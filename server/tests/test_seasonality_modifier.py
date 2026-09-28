"""Tests for the seasonality modifier computation in the green-score.

The seasonality modifier rewards recipes whose fresh-plant ingredients (fruit
and vegetables) are in season, and penalises those that are not. It is computed
by :func:`api.score.global_seasonality_modifier` from the recipe ingredients
alone (no taxonomy lookup), so the pure-function tests below build ingredients
directly without mocking the Agribalyse index.

The integration tests go through :func:`api.score.compute_green_score` end to
end and check that the modifier is both returned in the response and applied to
the numeric score.
"""

import pytest

from api import score, types
from api.score_data import DEFAULT_DISTANCE_MODIFIER
from api.score_types import RecipeMetrics
from tests.helpers import (
    WORLD_EPI_MODIFIER,
    build_ingredient_obj,
    create_taxonomy,
    create_taxonomy_node,
    patch_ingredients_taxonomy,
    patch_labels_taxonomy,
)

# Maximum bonus granted when every fresh-plant ingredient is in season.
MAX_SEASONALITY_BONUS = 5.0
# Maximum malus applied when no fresh-plant ingredient is in season (ratio 0).
MAX_SEASONALITY_MALUS = -10.0


def _fresh_plant(id_: str, weight: float, *, in_season: bool) -> types.RecipeIngredientInput:
    """Build a fresh-plant ingredient for the pure unit tests.

    The ``taxonomy_id`` is irrelevant here because ``global_seasonality_modifier``
    only reads ``weight``, ``is_fresh_plant`` and ``is_in_season``.
    """
    return build_ingredient_obj(
        id_,
        name=id_,
        taxonomy_id="en:apple",
        weight=weight,
        is_fresh_plant=True,
        is_in_season=in_season,
    )


# --- global_seasonality_modifier (pure unit tests) ------------------------


def test_global_seasonality_modifier_no_fresh_plant():
    """With no fresh-plant ingredient the modifier is 0 (neutral)."""
    recipe = [build_ingredient_obj("i1", "flour", "en:wheat-flour", weight=200)]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == 0.0
    assert recipe_metrics.notes == [
        "No fresh produce ingredients: no seasonality bonus/malus"
    ]


def test_global_seasonality_modifier_empty_recipe():
    """An empty ingredient list is neutral (0)."""
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier([], recipe_metrics) == 0.0
    assert recipe_metrics.notes == [
        "No fresh produce ingredients: no seasonality bonus/malus"
    ]


def test_global_seasonality_modifier_all_in_season():
    """All fresh-plant ingredients in season -> maximum bonus (+5)."""
    recipe = [
        _fresh_plant("i1", 100, in_season=True),
        _fresh_plant("i2", 300, in_season=True),
    ]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(
        MAX_SEASONALITY_BONUS
    )
    assert recipe_metrics.notes == [
        "All fresh produce ingredients are in season: maximum seasonality bonus"
    ]


def test_global_seasonality_modifier_single_in_season():
    """A single in-season fresh plant also gets the maximum bonus."""
    recipe = [_fresh_plant("i1", 100, in_season=True)]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(
        MAX_SEASONALITY_BONUS
    )
    assert recipe_metrics.notes == [
        "All fresh produce ingredients are in season: maximum seasonality bonus"
    ]


def test_global_seasonality_modifier_none_in_season():
    """No fresh-plant ingredient in season -> maximum malus (-10, ratio 0)."""
    recipe = [
        _fresh_plant("i1", 100, in_season=False),
        _fresh_plant("i2", 300, in_season=False),
    ]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(
        MAX_SEASONALITY_MALUS
    )
    # the partial / off-season branch does not emit a note
    assert recipe_metrics.notes is None


def test_global_seasonality_modifier_partial_in_season():
    """Half the fresh-plant weight in season -> ratio 0.5 -> malus -5.

    modifier = -10 * (1 - ratio) = -10 * (1 - 0.5) = -5.0
    """
    recipe = [
        _fresh_plant("i1", 100, in_season=True),
        _fresh_plant("i2", 100, in_season=False),
    ]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(-5.0)
    # the partial / off-season branch does not emit a note
    assert recipe_metrics.notes is None


def test_global_seasonality_modifier_weighted_by_weight():
    """The ratio is weighted by weight, not by ingredient count.

    100g in season out of 400g fresh plant -> ratio 0.25 -> -7.5
    modifier = -10 * (1 - 0.25) = -7.5
    """
    recipe = [
        _fresh_plant("i1", 100, in_season=True),
        _fresh_plant("i2", 300, in_season=False),
    ]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(-7.5)
    # the partial / off-season branch does not emit a note
    assert recipe_metrics.notes is None


def test_global_seasonality_modifier_ignores_non_fresh_plant():
    """Non-fresh-plant ingredients are excluded from both numerator and denominator."""
    # 100g in-season fresh plant + 900g non-fresh flour: ratio is 1/1, not 1/10
    recipe = [
        _fresh_plant("i1", 100, in_season=True),
        build_ingredient_obj("i2", "flour", "en:wheat-flour", weight=900, is_in_season=False),
    ]
    recipe_metrics = RecipeMetrics()
    assert score.global_seasonality_modifier(recipe, recipe_metrics) == pytest.approx(
        MAX_SEASONALITY_BONUS
    )
    assert recipe_metrics.notes == [
        "All fresh produce ingredients are in season: maximum seasonality bonus"
    ]


# --- compute_green_score integration --------------------------------------


def _apple_taxonomy():
    """An ingredients taxonomy with a single scorable apple (EF score 0.3)."""
    return create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )


@pytest.mark.asyncio
async def test_compute_green_score_fresh_plant_in_season(agribalyse_index):
    """An in-season fresh plant adds the +5 bonus to the numeric score.

    apple alone (ef 0.3 -> normalized ~76.38), no origin, no labels:
    numeric = 76.38 + 0 (labels) + (-3) (epi world) + (-7) (distance world) + 5
            = 71.38
    """
    labels_taxonomy = create_taxonomy({})
    recipe = [
        build_ingredient_obj("i1", "apple", "en:apple", is_fresh_plant=True, is_in_season=True)
    ]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.seasonality_modifier == pytest.approx(MAX_SEASONALITY_BONUS)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3)
        + WORLD_EPI_MODIFIER
        + DEFAULT_DISTANCE_MODIFIER
        + MAX_SEASONALITY_BONUS
    )
    # the in-season branch emits a recipe-level seasonality note
    assert result.notes == [
        "All fresh produce ingredients are in season: maximum seasonality bonus"
    ]
    # the apple has no origin, so per-ingredient notes are populated
    assert "i1" in result.ingredients_notes
    assert result.ingredients_notes["i1"]
    """An off-season fresh plant applies the -10 malus to the numeric score.

    numeric = 76.38 + 0 + (-3) + (-7) + (-10) = 56.38
    """
    labels_taxonomy = create_taxonomy({})
    recipe = [
        build_ingredient_obj("i1", "apple", "en:apple", is_fresh_plant=True, is_in_season=False)
    ]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.seasonality_modifier == pytest.approx(MAX_SEASONALITY_MALUS)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3)
        + WORLD_EPI_MODIFIER
        + DEFAULT_DISTANCE_MODIFIER
        + MAX_SEASONALITY_MALUS
    )
    # the off-season branch does not emit a recipe-level note
    assert result.notes is None
    # the apple still has per-ingredient notes (no origin)
    assert "i1" in result.ingredients_notes
    assert result.ingredients_notes["i1"]
    """A non-fresh ingredient yields a neutral (0) seasonality modifier."""
    labels_taxonomy = create_taxonomy({})
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]
    with (
        patch_ingredients_taxonomy(_apple_taxonomy()),
        patch_labels_taxonomy(labels_taxonomy),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.seasonality_modifier == pytest.approx(0.0)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3) + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )
    # no fresh produce -> the neutral branch emits its own recipe-level note
    assert result.notes == [
        "No fresh produce ingredients: no seasonality bonus/malus"
    ]


@pytest.mark.asyncio
async def test_compute_green_score_all_missing_seasonality_none(agribalyse_index):
    """When no ingredient is scorable, seasonality_modifier is None (not 0)."""
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water")})
    recipe = [
        build_ingredient_obj("i1", "water", "en:water", is_fresh_plant=True, is_in_season=True)
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.global_ef_score is None
    assert result.seasonality_modifier is None
    assert result.numeric_score is None
    # nothing is scorable -> no notes are gathered
    assert result.notes is None
    assert result.ingredients_notes is None
