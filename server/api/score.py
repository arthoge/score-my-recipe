"""Green-score computation business logic."""

import logging
import math
from typing import Optional

import openfoodfacts.taxonomy as taxonomy
from async_lru import alru_cache as async_cache

import api.agribalyse as agribalyse
import api.off as off
import api.score_types as score_types
import api.score_data as score_data

import api.types as types

logger = logging.getLogger(__name__)


def safe_zip_recipe_metrics(recipe: types.RecipeInput, recipe_metrics: score_types.RecipeMetrics):
    """Zip a recipe and its metrics, checking that they have the same ingredient ids at each line.

    Raises a ValueError if the lengths differ or some ingredients does not match.
    """
    metrics = recipe_metrics.metrics
    if len(recipe) != len(metrics):
        raise ValueError(
            f"Recipe and metrics have different lengths: {len(recipe)} vs {len(metrics)}"
        )
    if any(ingredient.id != metric.id for ingredient, metric in zip(recipe, metrics)):
        raise ValueError("Recipe and metrics have different ingredient ids")
    return zip(recipe, metrics)


async def match_ingredients_to_agribalyse(
    recipe: types.RecipeInput,
) -> dict[str, types.IngredientAgribalyse]:
    """Compute (for now: gather Agribalyse data for) the green-score of a recipe.

    Each ingredient is looked up in the ingredients taxonomy; its code properties
    (searched on the node and its parents) are used, in priority order, to find
    the matching Agribalyse row.
    """
    ingredients_taxonomy = await off.get_ingredients_taxonomy()
    results: dict[str, types.IngredientAgribalyse] = {}

    for ingredient in recipe:
        node: Optional[taxonomy.TaxonomyNode] = None
        taxonomy_id = ingredient.codified_ingredient.id if ingredient.codified_ingredient else None
        if taxonomy_id and taxonomy_id in ingredients_taxonomy:
            node = ingredients_taxonomy[taxonomy_id]

        code, source, row = agribalyse.find_agribalyse_row(node)
        results[ingredient.id] = types.IngredientAgribalyse(
            id=ingredient.id,
            name=ingredient.name,
            matched_code=code,
            code_source=source,
            agribalyse=row,
        )
    return results


async def gather_ef_metrics(
    recipe: types.RecipeInput,
) -> score_types.RecipeMetrics:
    """Gather the per-ingredient EF score from Agribalyse.

    Negative weights are invalid and raise a ``ValueError``. A zero weight is
    tolerated (it does not perturb the computation).
    """
    ingredients_agribalyse = await match_ingredients_to_agribalyse(recipe)
    metrics: list[score_types.IngredientMetrics] = []
    for ingredient in recipe:
        if ingredient.weight < 0:
            raise ValueError(
                f"Ingredient {ingredient.id} has negative weight {ingredient.weight}, cannot compute EF score."
            )
        agribalyse_row = ingredients_agribalyse[ingredient.id].agribalyse
        ef_score: Optional[float] = None
        missing = True
        if agribalyse_row and (score_str := agribalyse_row.get("score")):
            ef_score = float(score_str)
            missing = False
        metrics.append(
            score_types.IngredientMetrics(
                id=ingredient.id,
                weight=ingredient.weight,
                ef_score=ef_score,
                missing=missing,
            )
        )
    return score_types.RecipeMetrics(metrics=metrics)


def compute_ratios(
    recipe_metrics: score_types.RecipeMetrics,
    ratio_mode: score_types.AccountedWeights = score_types.AccountedWeights.ONLY_SCORABLE,
) -> None:
    """Compute each ingredient's weight ratio and EF contribution.

    The denominator depends on ``accounted_weights`` (see :class:`AccountedWeights`)

    Missing ingredients keep a ``None`` ratio and contribution. When the
    denominator is zero (no scorable ingredient / empty recipe), all ratios
    stay ``None``.
    """
    metrics = recipe_metrics.metrics
    if ratio_mode == score_types.AccountedWeights.ALL_WEIGHTS:
        total_weight = sum(m.weight for m in metrics)
    else:
        total_weight = sum(m.weight for m in metrics if not m.missing)

    if total_weight == 0:
        return

    for m in metrics:
        if m.missing:
            continue
        m.ratio = m.weight / total_weight


def ponderated_ef_sum(
    recipe_metrics: score_types.RecipeMetrics,
) -> Optional[float]:
    """Third pass: sum the per-ingredient EF contributions into the recipe EF score.

    Returns ``None`` when no ingredient contributes (all missing or empty
    recipe).
    """
    total = 0.0
    has_contribution = False
    for m in recipe_metrics.metrics:
        if m.ratio is not None and m.ef_score is not None:
            total += m.ef_score * m.ratio
            has_contribution = True
    return total if has_contribution else None


def normalize_ef_score(ef_score: float) -> float:
    """Normalize the EF score to a 0-100 scale.

    The normalization is based on the maximum EF score observed in the Agribalyse database.
    """
    # normalize the EF score to a 0-100 scale
    numerator = math.log(10 * ef_score + 1)
    divisor = math.log(2 + 1 / (100 * ef_score**4))
    normalized_score = 100 - numerator / divisor * 20
    return min(max(normalized_score, 0.0), 100.0)


@async_cache(maxsize=1)
async def labels_bonus_full() -> dict[str, int]:
    """Return the labels bonus dictionary, including all children of the listed labels."""
    taxonomy = await off.get_labels_taxonomy()
    labels_bonus_full = dict(score_data.LABELS_BONUS)
    for label_id, bonus in score_data.LABELS_BONUS.items():
        try:
            node = taxonomy[label_id]
        except KeyError:
            node = None
        if not node:
            logger.warning("Label %s not found in taxonomy", label_id)
            continue
        for child in node.get_children_hierarchy():
            labels_bonus_full[child.id] = max(labels_bonus_full.get(child.id, -1), bonus)
    return labels_bonus_full


@async_cache(maxsize=1)
async def labels_bonus_ingredients_restrictions_full() -> dict[str, list[str]]:
    """Return the labels bonus restrictions dictionary, including all children of the listed labels."""
    taxonomy = await off.get_ingredients_taxonomy()
    restrictions_full: dict[str, list[str]] = {}
    for label_id, ingredient_ids in score_data.LABELS_BONUS_INGREDIENTS_RESTRICTIONS.items():
        if not ingredient_ids:
            continue
        label_restrictions = set(ingredient_ids)
        for ingredient_id in ingredient_ids:
            try:
                node = taxonomy[ingredient_id]
            except KeyError:
                node = None
            if not node:
                logger.warning(
                    "Ingredient %s, restricting label %s, not found in taxonomy",
                    ingredient_id,
                    label_id,
                )
                continue
            label_restrictions.update(child.id for child in node.get_children_hierarchy())
        restrictions_full[label_id] = list(label_restrictions)
    return restrictions_full


async def gather_labels_bonus(
    recipe: types.RecipeInput, recipe_metrics: score_types.RecipeMetrics
) -> None:
    """Gather the bonus points from labels for the recipe.

    The bonus is the maximum of the bonuses of all ingredients.
    """
    labels_bonus = await labels_bonus_full()
    labels_restrictions = await labels_bonus_ingredients_restrictions_full()
    for ingredient, metric in safe_zip_recipe_metrics(recipe, recipe_metrics):
        if metric.missing or not ingredient.labels:
            continue
        # filter some labels based on the ingredient type, if needed
        labels_to_apply = []
        for label in ingredient.labels:
            if label.id in labels_restrictions:
                if (
                    ingredient.codified_ingredient
                    and ingredient.codified_ingredient.id not in labels_restrictions[label.id]
                ):
                    metric.add_note(
                        f"Label {label.id} bonus does not apply to ingredient {ingredient.codified_ingredient.id}"
                    )
                    continue
            labels_to_apply.append(label.id)
        if not labels_to_apply:
            continue
        max_bonus = max(labels_bonus.get(label_id, -1) for label_id in labels_to_apply)
        if max_bonus > 0:
            metric.labels_bonus = max_bonus


async def gather_epi_modifiers(
    recipe: types.RecipeInput, recipe_metrics: score_types.RecipeMetrics
):
    """Gather the EPI bonus/malus points from origins for the recipe.

    No origins is equivalent to world, that is the worst case.
    """
    epi_modifiers = await score_data.get_epi_modifiers()
    for ingredient, metric in safe_zip_recipe_metrics(recipe, recipe_metrics):
        if metric.missing:
            continue
        if not ingredient.origin:
            metric.add_note("EPI modifier: no origin provided, defaulting to world")
            modifier = epi_modifiers["en:world"]
        elif ingredient.origin.id not in epi_modifiers:
            metric.add_note("EPI modifier: EPI score for  origins not found, defaulting to world")
            modifier = epi_modifiers["en:world"]
        else:
            modifier = epi_modifiers[ingredient.origin.id]
        metric.epi_modifier = modifier


async def gather_distances_modifiers(
    recipe: types.RecipeInput,
    recipe_metrics: score_types.RecipeMetrics,
    country: Optional[str] = None,
):
    """Gather the distance bonus/malus points from origins for the recipe.

    No origins is equivalent to world, that is the worst case.
    No country means world for every ingredient
    """
    origins_by_country = await off.origins_by_country_code()
    origin_to_country_origin = await off.origin_to_country_origin()
    country_id = origins_by_country.get(country.upper()) if country else None
    distances_modifiers = await score_data.get_distances_modifiers()
    for ingredient, metric in safe_zip_recipe_metrics(recipe, recipe_metrics):
        if metric.missing:
            continue
        elif not country_id:
            metric.add_note(
                "Distance modifier: no country provided for recipe, defaulting to world"
            )
            modifier = score_data.DEFAULT_DISTANCE_MODIFIER
        elif not ingredient.origin or not ingredient.origin.id:
            metric.add_note("Distance modifier: no origin provided, defaulting to world")
            modifier = score_data.DEFAULT_DISTANCE_MODIFIER
        else:
            country_origin_id = origin_to_country_origin.get(ingredient.origin.id)
            if (
                country_origin_id is None
                or (country_id, country_origin_id) not in distances_modifiers
            ):
                metric.add_note(
                    "Distance modifier: distance score for origins not found, defaulting to world"
                )
                modifier = score_data.DEFAULT_DISTANCE_MODIFIER
            else:
                modifier = distances_modifiers[(country_id, country_origin_id)]
        metric.distance_modifier = modifier


def global_labels_bonus(recipe_metrics: score_types.RecipeMetrics) -> float:
    """Compute the global labels bonus for the recipe.

    The global bonus is the weighted average of the per-ingredient bonuses.
    """
    bonuses = [
        m.labels_bonus * m.ratio
        for m in recipe_metrics.metrics
        if m.labels_bonus is not None and m.ratio is not None
    ]
    return sum(bonuses) if bonuses else 0.0


def global_epi_modifier(recipe_metrics: score_types.RecipeMetrics) -> Optional[float]:
    """Compute the global EPI modifier for the recipe.

    The global modifier is the weighted average of the per-ingredient modifiers.
    """
    modifiers = [
        m.epi_modifier * m.ratio
        for m in recipe_metrics.metrics
        if m.epi_modifier is not None and m.ratio is not None
    ]
    return sum(modifiers) if modifiers else None


def global_distance_modifier(recipe_metrics: score_types.RecipeMetrics) -> Optional[float]:
    """Compute the global distance modifier for the recipe.

    The global modifier is the weighted average of the per-ingredient modifiers.
    """
    modifiers = [
        m.distance_modifier * m.ratio
        for m in recipe_metrics.metrics
        if m.distance_modifier is not None and m.ratio is not None
    ]
    return sum(modifiers) if modifiers else None


def global_seasonality_modifier(
    recipe: types.RecipeInput, recipe_metrics: score_types.RecipeMetrics
) -> float:
    """Gather the seasonality bonus/malus points.

    This is a global modifier based only on fresh vegetables and fruits
    """
    # first compute ratio among fresh produce ingredients
    total_fresh_plant_weight = sum(
        ingredient.weight for ingredient in recipe if ingredient.is_fresh_plant
    )
    if total_fresh_plant_weight == 0:
        recipe_metrics.add_note("No fresh produce ingredients: no seasonality bonus/malus")
        return 0.0
    total_in_season_weight = sum(
        ingredient.weight
        for ingredient in recipe
        if ingredient.is_fresh_plant and ingredient.is_in_season
    )
    # all fresh produce ingredients are in season, return the maximum bonus
    if total_fresh_plant_weight == total_in_season_weight:
        recipe_metrics.add_note(
            "All fresh produce ingredients are in season: maximum seasonality bonus"
        )
        return 5.0
    else:
        ratio = total_in_season_weight / total_fresh_plant_weight
        return -10 * (1 - ratio)


def score_to_letter(score: float) -> str:
    """Convert a score to a letter grade (A, B, C, D, E)"""
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 45:
        return "C"
    elif score >= 30:
        return "D"
    elif score >= 15:
        return "E"
    else:
        return "F"


async def compute_green_score(
    recipe: types.RecipeInput,
    country: Optional[str] = None,
    accounted_weights: score_types.AccountedWeights = score_types.AccountedWeights.ONLY_SCORABLE,
) -> types.GreenScoreResponse:
    """Compute (for now: gather Agribalyse data for) the green-score of a recipe.

    Each ingredient is looked up in the ingredients taxonomy; its code properties
    (searched on the node and its parents) are used, in priority order, to find
    the matching Agribalyse row.
    """
    # TODO handle exceptions
    # compute the EF score for the recipe
    recipe_metrics = await gather_ef_metrics(recipe)
    compute_ratios(recipe_metrics, accounted_weights)
    await gather_labels_bonus(recipe, recipe_metrics)
    await gather_epi_modifiers(recipe, recipe_metrics)
    await gather_distances_modifiers(recipe, recipe_metrics, country)
    ef_score = ponderated_ef_sum(recipe_metrics)
    missing_ingredient_ids = [m.id for m in recipe_metrics.metrics if m.missing]
    if ef_score is not None:
        normalized_ef_score = normalize_ef_score(ef_score)
        # account for bonus / malus
        labels_bonus = global_labels_bonus(recipe_metrics)
        epi_modifier = global_epi_modifier(recipe_metrics)
        distances_modifier = global_distance_modifier(recipe_metrics)
        seasonality_modifier = global_seasonality_modifier(recipe, recipe_metrics)
        # TODO account for packaging in the green-score computation
        numeric_score = (
            normalized_ef_score
            + labels_bonus
            + (epi_modifier or 0.0)
            + (distances_modifier or 0.0)
            + seasonality_modifier
        )
        # normalize to 0-100 range
        numeric_score = min(max(numeric_score, 0.0), 100.0)
        letter_grade = score_to_letter(numeric_score)
        notes = recipe_metrics.notes
        ingredients_notes = recipe_metrics.ingredients_notes
    else:
        normalized_ef_score = None
        labels_bonus = None
        epi_modifier = None
        distances_modifier = None
        seasonality_modifier = None
        numeric_score = None
        letter_grade = None
        notes = None
        ingredients_notes = None
    return types.GreenScoreResponse(
        global_ef_score=ef_score,
        labels_bonus=labels_bonus,
        epi_modifier=epi_modifier,
        distances_modifier=distances_modifier,
        seasonality_modifier=seasonality_modifier,
        numeric_score=numeric_score,
        letter_grade=letter_grade,
        missing_ingredient_ids=missing_ingredient_ids,
        notes=notes,
        ingredients_notes=ingredients_notes,
    )
