"""Bounded, recipe-level simulations of catalog-discovered alternatives and comparable OFF products."""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel, Field

from api import agribalyse, ciqual, nutrition_data, off, references
from api.improvement_candidates import can_reduce, discover_food_codes
from api.recipe_analysis import ExportIngredient, ExportRecipe, calculate_report

logger = logging.getLogger(__name__)
MAX_ROWS = 100
MAX_CANDIDATES = 60


class ImprovementRequest(BaseModel):
    """Complete recipe inputs, with a language for names and product search."""

    recipe: ExportRecipe
    lang: str = Field(default="en", pattern=r"^[a-z]{2}$")


class ScoreChange(BaseModel):
    """Directional numeric-score change; null percentage when the baseline is zero.

    Green Score increases; Nutri-Score points decrease. Percent uses the absolute
    baseline so negative Nutri-Score points retain the correct improvement sign.
    """

    before: float
    after: float
    before_grade: str
    after_grade: str
    percent: float | None
    excluded_count: int = 0


class ImprovementSuggestion(BaseModel):
    """A resolved replacement tied to exactly one ingredient row."""

    id: str
    ingredient_id: str
    category: Literal["ingredient", "open_food_facts"]
    before: ExportIngredient
    after: ExportIngredient
    ciqual_name: str | None = None
    agribalyse_name: str | None = None
    product_name: str | None = None
    green_score: ScoreChange | None
    nutri_score: ScoreChange | None


class ImprovementResponse(BaseModel):
    """Safe candidates; unavailable dependencies are distinct from an empty search."""

    suggestions: list[ImprovementSuggestion] = Field(default_factory=list)
    unavailable: bool = False
    limited: bool = False
    reason: (
        Literal["no_candidates", "scores_unavailable", "no_improvement", "references_missing"]
        | None
    ) = None


class OptimizeRequest(ImprovementRequest):
    """Selected candidate identifiers are validated against the current recipe."""

    selected_ids: list[str] = Field(min_length=1, max_length=100)


class OptimizeResponse(BaseModel):
    """The combined replacement recipe, recalculated before applying any changes."""

    recipe: ExportRecipe


def green_exclusions(report) -> set[str]:
    """Ignore unused rows when comparing the ingredients covered by environmental scores."""
    recipe, green, _ = report
    missing = set(green.missing_ingredient_ids) if green else set()
    if recipe is not None:
        active = {
            row.id for row in recipe.ingredients if row.quantity_g is None or row.quantity_g > 0
        }
        missing &= active
    return missing


def score_changes(before, after) -> tuple[ScoreChange | None, ScoreChange | None, bool]:
    """Compare identical coverage, expose trade-offs and reject newly excluded rows.

    Partial scores are comparable when the same rows are excluded on both sides.
    Added coverage is useful but cannot be presented as a percentage improvement;
    newly missing coverage must never create an apparent gain.
    """
    changes = []
    coverage_preserved = True
    for index, direction in ((1, 1), (2, -1)):
        old, new = before[index], after[index]
        if index == 1:
            valid_old = (
                old is not None and old.numeric_score is not None and old.letter_grade is not None
            )
            valid_new = (
                new is not None and new.numeric_score is not None and new.letter_grade is not None
            )
            old_exclusions, new_exclusions = green_exclusions(before), green_exclusions(after)
            old_score, new_score = (
                (old.numeric_score if valid_old else None),
                (new.numeric_score if valid_new else None),
            )
            old_grade, new_grade = (
                (old.letter_grade if valid_old else None),
                (new.letter_grade if valid_new else None),
            )
        else:
            valid_old = (
                old is not None
                and old.status in ("complete", "partial")
                and old.nutri_score is not None
            )
            valid_new = (
                new is not None
                and new.status in ("complete", "partial")
                and new.nutri_score is not None
            )
            old_exclusions = (
                {row.ingredient_id for row in old.excluded_ingredients} if old else set()
            )
            new_exclusions = (
                {row.ingredient_id for row in new.excluded_ingredients} if new else set()
            )
            old_score, new_score = (
                (old.nutri_score.score if valid_old else None),
                (new.nutri_score.score if valid_new else None),
            )
            old_grade, new_grade = (
                (old.nutri_score.grade if valid_old else None),
                (new.nutri_score.grade if valid_new else None),
            )
        if valid_old and (not valid_new or new_exclusions - old_exclusions):
            coverage_preserved = False
        if not valid_old or not valid_new or old_exclusions != new_exclusions:
            changes.append(None)
            continue
        delta = direction * (new_score - old_score)
        changes.append(
            ScoreChange(
                before=old_score,
                after=new_score,
                before_grade=old_grade,
                after_grade=new_grade,
                percent=round(delta / abs(old_score) * 100, 1) if old_score else None,
                excluded_count=len(old_exclusions),
            )
        )
    return changes[0], changes[1], coverage_preserved


async def compare_reports(before, after):
    """Keep baseline ingredient coverage when a replacement resolves previously missing data.

    Extra coverage changes the score denominator. Recalculate that dimension on
    the original included rows, rather than confusing added coverage with a gain.
    This also makes selected swaps with different coverage changes comparable.
    """
    initial = score_changes(before, after)
    if not initial[2]:
        return initial
    aligned = list(after)
    for index in (1, 2):
        old, new = before[index], after[index]
        if index == 1:
            if old is None or old.numeric_score is None or new is None or new.numeric_score is None:
                continue
            old_missing, new_missing = green_exclusions(before), green_exclusions(after)
        else:
            if old is None or old.nutri_score is None or new is None or new.nutri_score is None:
                continue
            old_missing = {row.ingredient_id for row in old.excluded_ingredients}
            new_missing = {row.ingredient_id for row in new.excluded_ingredients}
        if not old_missing - new_missing or after[0] is None:
            continue
        restricted = after[0].model_copy(deep=True)
        restricted.ingredients = [
            row for row in restricted.ingredients if row.id not in old_missing
        ]
        if not restricted.ingredients:
            continue
        recalculated = (await calculate_report(restricted))[index]
        if index == 1 and recalculated is not None:
            aligned[index] = recalculated.model_copy(
                update={
                    "missing_ingredient_ids": sorted(
                        old_missing | set(recalculated.missing_ingredient_ids)
                    )
                }
            )
        elif recalculated is not None:
            aligned[index] = recalculated.model_copy(
                update={
                    "status": "partial" if recalculated.nutri_score else recalculated.status,
                    "excluded_ingredients": [
                        *old.excluded_ingredients,
                        *recalculated.excluded_ingredients,
                    ],
                }
            )
        else:
            aligned[index] = None
    return score_changes(before, aligned)


def has_regression(green: ScoreChange | None, nutri: ScoreChange | None) -> bool:
    """Identify a displayed trade-off, even when the percentage baseline is zero."""
    return bool(
        (green and green.after < green.before - 1e-8) or (nutri and nutri.after > nutri.before)
    )


def improves(green: ScoreChange | None, nutri: ScoreChange | None) -> bool:
    """Require a measured improvement, even when a zero baseline has no percentage."""
    return bool(
        (green and green.after > green.before + 1e-8) or (nutri and nutri.after < nutri.before)
    )


def food_candidates(row: ExportIngredient, lang: str) -> list[ImprovementSuggestion]:
    """Discover alternatives using food composition, categories and preparation."""
    candidates = []
    # Measured masses and unsupported cooking transformations cannot be reused.
    # Catalog preparation compatibility is checked before returning alternatives.
    if row.preparation != "none" or row.prepared_weight_g is not None or row.state != "raw":
        return candidates
    environmental_scores = {
        str(item["ciqual_code"]): float(item["score"])
        for item in agribalyse.get_reference_rows()
        if item.get("ciqual_code") and item.get("score") is not None
    }
    codes = discover_food_codes(row.ciqual_code, environmental_scores)
    for code in codes:
        food = ciqual.get_foods().get(code)
        if not food or code not in nutrition_data.get_foods():
            continue
        environmental = [
            r
            for r in agribalyse.get_reference_rows()
            if str(r.get("ciqual_code")) == code and r.get("score") is not None
        ]
        environmental.sort(key=lambda r: str(r["code"]))
        reference = environmental[0] if environmental else None
        name = ciqual.food_name(food, lang)
        replacement = row.model_copy(
            deep=True,
            update={
                "name": name,
                "ciqual_code": code,
                "barcode": None,
                "codified_ingredient": None,
                "agribalyse_code": str(reference["code"]) if reference else None,
                "labels": [],
                "origin": None,
                "is_fresh_plant": False,
                "is_in_season": False,
            },
        )
        candidates.append(
            ImprovementSuggestion(
                id=f"{row.id}:ciqual:{code}",
                ingredient_id=row.id,
                category="ingredient",
                before=row,
                after=replacement,
                ciqual_name=name,
                agribalyse_name=str(reference.get("name_fr") or reference.get("lci_name"))
                if reference
                else None,
                green_score=None,
                nutri_score=None,
            )
        )
    if row.state == "raw" and row.quantity_g and can_reduce(row.ciqual_code):
        for fraction in (0.9, 0.8):
            quantity = round(row.quantity_g * fraction, 2)
            if not 0 < quantity < row.quantity_g:
                continue
            replacement = row.model_copy(
                deep=True,
                update={
                    "quantity_g": quantity,
                },
            )
            candidates.append(
                ImprovementSuggestion(
                    id=f"{row.id}:quantity:{fraction}",
                    ingredient_id=row.id,
                    category="ingredient",
                    before=row,
                    after=replacement,
                    ciqual_name=ciqual.food_name(ciqual.get_foods()[row.ciqual_code], lang)
                    if row.ciqual_code in ciqual.get_foods()
                    else None,
                    green_score=None,
                    nutri_score=None,
                )
            )
    return candidates


async def product_candidates(row: ExportIngredient, lang: str) -> list[ImprovementSuggestion]:
    """Search real products sharing the original product's most specific category."""
    if (
        not row.barcode
        or row.preparation != "none"
        or row.state != "raw"
        or row.prepared_weight_g is not None
    ):
        return []
    product = await nutrition_data.get_product(row.barcode)
    categories = product.get("categories_tags", []) if product else []
    if not categories:
        return []
    category = categories[-1]
    hits = await off.search_products(row.name, lang, 3)
    candidates = []
    for hit in hits:
        code = hit.get("code")
        if not isinstance(code, str) or not code.isdigit() or code == row.barcode:
            continue
        if category not in hit.get("categories_tags", []):
            continue
        name = hit.get(f"product_name_{lang}") or hit.get("product_name")
        if not isinstance(name, str) or not name.strip():
            continue
        # The generic ingredient correspondence stays the same. Certifications and
        # provenance of the old branded product cannot be claimed for the new one.
        replacement = row.model_copy(
            deep=True,
            update={
                "barcode": code,
                "ciqual_code": None,
                "labels": [],
                "origin": None,
            },
        )
        candidates.append(
            ImprovementSuggestion(
                id=f"{row.id}:off:{code}",
                ingredient_id=row.id,
                category="open_food_facts",
                before=row,
                after=replacement,
                product_name=name.strip(),
                green_score=None,
                nutri_score=None,
            )
        )
    return candidates


async def resolve_recipe_references(recipe: ExportRecipe, lang: str) -> tuple[ExportRecipe, bool]:
    """Fill missing references before comparing; never overwrite user-selected foods.

    The dialog must not depend on the editor finishing its reference requests.
    Use an explicit environmental correspondence first, then the existing taxonomy
    resolver. Unrecognized free text remains unknown rather than guessing a food.
    """
    resolved = recipe.model_copy(deep=True)
    unavailable = False
    semaphore = asyncio.Semaphore(4)

    async def resolve(row):
        nonlocal unavailable
        if row.ciqual_code or row.barcode or not row.quantity_g:
            return
        if row.agribalyse_code:
            match = next(
                (
                    item
                    for item in agribalyse.get_reference_rows()
                    if str(item["code"]) == row.agribalyse_code
                ),
                None,
            )
            code = str(match.get("ciqual_code")) if match else None
            if code in ciqual.get_foods():
                row.ciqual_code = code
                return
        taxonomy = row.codified_ingredient
        if not taxonomy or not taxonomy.id or not taxonomy.is_in_taxonomy:
            return
        async with semaphore:
            try:
                match = await asyncio.wait_for(
                    references.ingredient_references(taxonomy.id, lang), 15
                )
                if match.ciqual:
                    row.ciqual_code = match.ciqual.code
                if not row.agribalyse_code and match.agribalyse:
                    row.agribalyse_code = match.agribalyse.code
            except (OSError, ValueError, TimeoutError) as error:
                logger.warning("Improvement reference resolution unavailable: %s", error)
                unavailable = True

    await asyncio.gather(*(resolve(row) for row in resolved.ingredients))
    return resolved, unavailable


async def find_improvements(request: ImprovementRequest) -> ImprovementResponse:
    """Simulate candidates independently, bounded to sixty with four concurrent tasks."""
    resolved, references_unavailable = await resolve_recipe_references(request.recipe, request.lang)
    baseline = await calculate_report(resolved)
    response = ImprovementResponse(
        unavailable=references_unavailable
        or baseline[1] is None
        or baseline[2] is None
        or baseline[2].status == "dependency_error"
    )
    semaphore = asyncio.Semaphore(4)

    async def candidates(row):
        """Keep one unavailable product service from hiding local food candidates."""
        async with semaphore:
            try:
                local = food_candidates(row, request.lang)
                if row.barcode:
                    try:
                        local.extend(
                            await asyncio.wait_for(product_candidates(row, request.lang), 15)
                        )
                    except (OSError, ValueError, TimeoutError) as error:
                        logger.warning("Product improvement candidates unavailable: %s", error)
                        response.unavailable = True
                return local
            except (OSError, ValueError, TimeoutError) as error:
                logger.warning("Improvement candidates unavailable: %s", error)
                response.unavailable = True
                return []

    rows = [row for row in resolved.ingredients if row.quantity_g and row.quantity_g > 0]
    lists = await asyncio.gather(*(candidates(row) for row in rows[:MAX_ROWS]))
    # Round-robin prevents the first ingredient from consuming the search budget.
    all_candidates = [
        group[index]
        for index in range(max((len(group) for group in lists), default=0))
        for group in lists
        if index < len(group)
    ]
    response.limited = len(rows) > MAX_ROWS or len(all_candidates) > MAX_CANDIDATES

    no_comparable_scores = True

    async def evaluate(candidate):
        """Retain replacements only when complete recipe scores verify the gain."""
        recipe = resolved.model_copy(deep=True)
        recipe.ingredients = [
            candidate.after if r.id == candidate.ingredient_id else r for r in recipe.ingredients
        ]
        nonlocal no_comparable_scores
        async with semaphore:
            result = await calculate_report(recipe)
            green, nutri, safe = await compare_reports(baseline, result)
        if green is not None or nutri is not None:
            no_comparable_scores = False
        if result[1] is None or result[2] is None or result[2].status == "dependency_error":
            response.unavailable = True
        if safe and improves(green, nutri):
            return candidate.model_copy(update={"green_score": green, "nutri_score": nutri})
        return None

    evaluated = await asyncio.gather(*(evaluate(c) for c in all_candidates[:MAX_CANDIDATES]))
    # Prefer an alternative without trade-offs; otherwise show its measured regression.
    best = {}
    for candidate in evaluated:
        if candidate is None:
            continue
        gain = sum(c.percent or 0 for c in (candidate.green_score, candidate.nutri_score) if c)
        rank = (not has_regression(candidate.green_score, candidate.nutri_score), gain)
        if candidate.ingredient_id not in best or rank > best[candidate.ingredient_id][0]:
            best[candidate.ingredient_id] = (rank, candidate)
    response.suggestions = [value[1] for value in best.values()]
    if not response.suggestions:
        if not all_candidates:
            if any(not row.ciqual_code and not row.barcode for row in rows):
                response.reason = "references_missing"
            else:
                response.reason = "scores_unavailable" if response.unavailable else "no_candidates"
        elif not any(c for c in evaluated) and no_comparable_scores:
            response.reason = "scores_unavailable"
        else:
            response.reason = "no_improvement"
    return response


async def optimize_recipe(request: OptimizeRequest) -> OptimizeResponse:
    """Validate selections and recheck their combined effect before returning a recipe."""
    available = await find_improvements(request)
    by_id = {suggestion.id: suggestion for suggestion in available.suggestions}
    if len(set(request.selected_ids)) != len(request.selected_ids) or any(
        selection not in by_id for selection in request.selected_ids
    ):
        raise ValueError("Selected suggestions are no longer available")
    replacements = {by_id[key].ingredient_id: by_id[key].after for key in request.selected_ids}
    resolved, _ = await resolve_recipe_references(request.recipe, request.lang)
    recipe = resolved.model_copy(deep=True)
    recipe.ingredients = [replacements.get(row.id, row) for row in recipe.ingredients]
    before, after = await asyncio.gather(calculate_report(resolved), calculate_report(recipe))
    green, nutri, safe = await compare_reports(before, after)
    if not safe or not improves(green, nutri):
        raise ValueError("Selected changes do not improve the combined recipe scores")
    return OptimizeResponse(recipe=recipe)
