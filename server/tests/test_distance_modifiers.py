"""Tests for the distance modifiers computation added to the green-score.

The distance modifiers are read from the real CSV data files shipped in the
repository (``data/greenscore-distances-scores.csv`` and
``data/greenscore-extended-distances-scores.csv``); we intentionally do **not**
patch the loading routines so the values are checked against the real data.
Only the ingredients/labels/epi taxonomies are mocked, as they are needed to
build the recipe metrics independently of the distance pass.
"""

import pytest

from api.score_data import DEFAULT_DISTANCE_MODIFIER
from api import score, score_data
from api.score_types import IngredientMetrics, RecipeMetrics
from tests.helpers import (
    FRANCE_DISTANCE_MODIFIER,
    WORLD_EPI_MODIFIER,
    build_ingredient_obj,
    create_taxonomy,
    create_taxonomy_node,
    patch_ingredients_taxonomy,
    patch_labels_taxonomy,
    patch_epi_modifiers,
)


# Real distance modifiers for a recipe evaluated in France (recipe country is
# the destination, ingredient origin is the source), taken from the CSV files:
GERMANY_DISTANCE_MODIFIER = -0.7
ARGENTINA_DISTANCE_MODIFIER = -7.0

# Country code used as the recipe evaluation country across the tests.
FRANCE_COUNTRY = "FR"

# A controlled EPI modifiers table so the EPI pass does not interfere with the
# distance assertions in the integration tests.
FRANCE_EPI_MODIFIER = 3.0
GERMANY_EPI_MODIFIER = 2.0
ARGENTINA_EPI_MODIFIER = -2.0
SAMPLE_EPI_MODIFIERS = {
    "en:world": WORLD_EPI_MODIFIER,
    "en:france": FRANCE_EPI_MODIFIER,
    "en:germany": GERMANY_EPI_MODIFIER,
    "en:argentina": ARGENTINA_EPI_MODIFIER,
}


def _apple_taxonomy() -> "object":
    """An ingredients taxonomy with a single scorable apple."""
    return create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )


# --- get_distances_modifiers ------------------------------------------------


@pytest.mark.asyncio
async def test_get_distances_modifiers_loads_real_csv():
    """The real data files are loaded into a (destination, source) -> modifier mapping."""
    score_data.get_distances_modifiers.cache_clear()
    modifiers = await score_data.get_distances_modifiers()
    # France -> France has the maximum distance score (100), hence a +3 modifier
    assert modifiers[("en:france", "en:france")] == pytest.approx(FRANCE_DISTANCE_MODIFIER)
    # at least one positive (local) and one negative (remote) modifier exists
    assert any(v > 0 for v in modifiers.values())
    assert any(v < 0 for v in modifiers.values())
    # all modifiers are numbers
    assert all(isinstance(v, float) for v in modifiers.values())


@pytest.mark.asyncio
async def test_get_distances_modifiers_real_values_for_france():
    """Modifiers for a recipe evaluated in France match the official reference values.

    The lookup key is ``(recipe_country, ingredient_origin)``: the recipe
    country is the destination, the ingredient origin is the source.
    """
    score_data.get_distances_modifiers.cache_clear()
    modifiers = await score_data.get_distances_modifiers()
    assert modifiers[("en:france", "en:france")] == pytest.approx(FRANCE_DISTANCE_MODIFIER)
    assert modifiers[("en:france", "en:germany")] == pytest.approx(GERMANY_DISTANCE_MODIFIER)
    assert modifiers[("en:france", "en:argentina")] == pytest.approx(ARGENTINA_DISTANCE_MODIFIER)


@pytest.mark.asyncio
async def test_get_distances_modifiers_is_cached():
    """The modifiers table is computed once and cached for subsequent calls."""
    score_data.get_distances_modifiers.cache_clear()
    first = await score_data.get_distances_modifiers()
    second = await score_data.get_distances_modifiers()
    assert first is second


# --- gather_distances_modifiers --------------------------------------------


@pytest.mark.asyncio
async def test_gather_distances_modifiers_no_country_defaults_to_world(agribalyse_index):
    """Without a recipe country, every ingredient falls back to the world modifier."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=None)
    assert recipe_metrics.metrics[0].distance_modifier == DEFAULT_DISTANCE_MODIFIER
    assert any("no country provided" in n for n in (recipe_metrics.metrics[0].notes or []))


@pytest.mark.asyncio
async def test_gather_distances_modifiers_known_origin_france(agribalyse_index):
    """A French ingredient in a French recipe gets the local (+3) modifier."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier == pytest.approx(FRANCE_DISTANCE_MODIFIER)
    assert recipe_metrics.metrics[0].notes is None


@pytest.mark.asyncio
async def test_gather_distances_modifiers_germany_from_france(agribalyse_index):
    """A German ingredient in a French recipe gets the -0.7 modifier."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:germany")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier == pytest.approx(GERMANY_DISTANCE_MODIFIER)
    assert recipe_metrics.metrics[0].notes is None


@pytest.mark.asyncio
async def test_gather_distances_modifiers_argentina_from_france(agribalyse_index):
    """An Argentine ingredient in a French recipe gets the -7 modifier (worst case)."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:argentina")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier == pytest.approx(ARGENTINA_DISTANCE_MODIFIER)
    assert recipe_metrics.metrics[0].notes is None


@pytest.mark.asyncio
async def test_gather_distances_modifiers_no_origin_defaults_to_world(agribalyse_index):
    """An ingredient without an origin falls back to the world modifier."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]  # no origin
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier == DEFAULT_DISTANCE_MODIFIER
    assert any("no origin provided" in n for n in (recipe_metrics.metrics[0].notes or []))


@pytest.mark.asyncio
async def test_gather_distances_modifiers_unknown_origin_defaults_to_world(agribalyse_index):
    """An origin absent from the distance table falls back to the world modifier."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:unknown-origin")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier == DEFAULT_DISTANCE_MODIFIER
    assert any("not found" in n for n in (recipe_metrics.metrics[0].notes or []))


@pytest.mark.asyncio
async def test_gather_distances_modifiers_skips_missing_ingredient(agribalyse_index):
    """A missing ingredient is skipped (no modifier, no note)."""
    ingredients_taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water")})
    recipe = [build_ingredient_obj("i1", "water", "en:water", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_distances_modifiers(recipe, recipe_metrics, country=FRANCE_COUNTRY)
    assert recipe_metrics.metrics[0].distance_modifier is None
    assert recipe_metrics.metrics[0].missing is True
    assert recipe_metrics.metrics[0].notes is None


# --- global_distance_modifier ----------------------------------------------


def test_global_distance_modifier_weighted_average():
    """The global modifier is the ratio-weighted average of per-ingredient modifiers."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(
                id="i1", weight=100, distance_modifier=FRANCE_DISTANCE_MODIFIER, ratio=0.25
            ),
            IngredientMetrics(
                id="i2", weight=300, distance_modifier=ARGENTINA_DISTANCE_MODIFIER, ratio=0.75
            ),
        ]
    )
    assert score.global_distance_modifier(recipe_metrics) == pytest.approx(
        FRANCE_DISTANCE_MODIFIER * 0.25 + ARGENTINA_DISTANCE_MODIFIER * 0.75
    )


def test_global_distance_modifier_none_when_no_modifiers():
    """With no modifier at all, the global modifier is None (not 0)."""
    recipe_metrics = RecipeMetrics(
        metrics=[IngredientMetrics(id="i1", weight=100, distance_modifier=None, ratio=1.0)]
    )
    assert score.global_distance_modifier(recipe_metrics) is None


def test_global_distance_modifier_ignores_missing_ratio():
    """Ingredients without a ratio (missing) don't contribute."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(
                id="i1", weight=100, distance_modifier=FRANCE_DISTANCE_MODIFIER, ratio=0.5
            ),
            IngredientMetrics(
                id="i2", weight=100, distance_modifier=ARGENTINA_DISTANCE_MODIFIER, ratio=None
            ),
        ]
    )
    assert score.global_distance_modifier(recipe_metrics) == pytest.approx(FRANCE_DISTANCE_MODIFIER * 0.5)


# --- compute_green_score integration --------------------------------------


@pytest.mark.asyncio
async def test_compute_green_score_applies_distance_modifier(agribalyse_index):
    """A known origin modifier is added to the numeric score.

    apple alone (ef 0.3) -> normalized ~76.38. With a France origin in a French
    recipe: numeric = 76.38 + 0 (labels) + 3 (epi) + 3 (distance) = 82.38.
    """
    labels_taxonomy = create_taxonomy({})
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country=FRANCE_COUNTRY)
    expected_ef = 0.3
    assert result.global_ef_score == pytest.approx(expected_ef)
    assert result.distances_modifier == pytest.approx(FRANCE_DISTANCE_MODIFIER)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + FRANCE_EPI_MODIFIER + FRANCE_DISTANCE_MODIFIER
    )


@pytest.mark.asyncio
async def test_compute_green_score_no_origin_uses_world_distance(agribalyse_index):
    """Without an origin, the world distance modifier (-7) is applied."""
    labels_taxonomy = create_taxonomy({})
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]  # no origin
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country=FRANCE_COUNTRY)
    assert result.distances_modifier == pytest.approx(DEFAULT_DISTANCE_MODIFIER)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3) + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )


@pytest.mark.asyncio
async def test_compute_green_score_no_country_uses_world_distance(agribalyse_index):
    """Without a recipe country, the distance modifier defaults to world."""
    labels_taxonomy = create_taxonomy({})
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country=None)
    assert result.distances_modifier == pytest.approx(DEFAULT_DISTANCE_MODIFIER)


@pytest.mark.asyncio
async def test_compute_green_score_all_missing_distance_modifier_none(agribalyse_index):
    """When no ingredient is scorable, distances_modifier is None (not 0)."""
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water")})
    recipe = [build_ingredient_obj("i1", "water", "en:water", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country=FRANCE_COUNTRY)
    assert result.global_ef_score is None
    assert result.distances_modifier is None
    assert result.numeric_score is None
    assert result.missing_ingredient_ids == ["i1"]


@pytest.mark.asyncio
async def test_compute_green_score_distance_weighted_by_ratio(agribalyse_index):
    """The global distance modifier is weighted by each ingredient's scorable ratio.

    apple 100g (France, +3) + pear 300g (Argentina, -7). Both scorable.
    global distance = (3 * 0.25) + (-7 * 0.75) = 0.75 - 5.25 = -4.5
    """
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:pear": create_taxonomy_node(
                "en:pear", properties={"agribalyse_food_code": {"en": "10002"}}
            ),
        }
    )
    recipe = [
        build_ingredient_obj("i_apple", "apple", "en:apple", weight=100, origin="en:france"),
        build_ingredient_obj("i_pear", "pear", "en:pear", weight=300, origin="en:argentina"),
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country=FRANCE_COUNTRY)
    # ratios: apple 0.25, pear 0.75
    expected_distance = FRANCE_DISTANCE_MODIFIER * 0.25 + ARGENTINA_DISTANCE_MODIFIER * 0.75
    expected_epi = FRANCE_EPI_MODIFIER * 0.25 + ARGENTINA_EPI_MODIFIER * 0.75
    assert result.distances_modifier == pytest.approx(expected_distance)
    expected_ef = 0.3 * 0.25 + 0.5 * 0.75
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + expected_epi + expected_distance
    )
