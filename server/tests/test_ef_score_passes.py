"""Tests for the multi-pass EF score computation in :mod:`api.score`."""

import pytest

from api.score_data import DEFAULT_DISTANCE_MODIFIER
from api import score
from api.score_types import IngredientMetrics, AccountedWeights, RecipeMetrics
from tests.helpers import (
    WORLD_EPI_MODIFIER,
    create_taxonomy,
    create_taxonomy_node,
    build_ingredient_obj,
    patch_ingredients_taxonomy,
)


# --- gather_ef_metrics ------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_marks_missing_ingredient(agribalyse_index):
    """An ingredient without an Agribalyse row is flagged missing, not dropped."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:water": create_taxonomy_node("en:water", properties={}),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        recipe_metrics = await score.gather_ef_metrics(
            [
                build_ingredient_obj("i_apple", "apple", "en:apple", weight=100),
                build_ingredient_obj("i_water", "water", "en:water", weight=50),
            ]
        )
    assert len(recipe_metrics.metrics) == 2
    apple = next(m for m in recipe_metrics.metrics if m.id == "i_apple")
    water = next(m for m in recipe_metrics.metrics if m.id == "i_water")
    assert apple.ef_score == pytest.approx(0.3)
    assert apple.missing is False
    assert water.ef_score is None
    assert water.missing is True


@pytest.mark.asyncio
async def test_gather_raises_on_negative_weight(agribalyse_index):
    """A negative weight is invalid and raises a ValueError in the gather pass."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        with pytest.raises(ValueError, match="negative weight"):
            await score.gather_ef_metrics(
                [build_ingredient_obj("i1", "apple", "en:apple", weight=-1)]
            )


def test_compute_ratios_scorable_denominator():
    """With the scorable denominator, contributions sum to the recipe EF score.

    apple: 100g * 0.3 = 30, pear: 300g * 0.5 = 150  -> ef 180 / 400 = 0.45
    """
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=0.3),
            IngredientMetrics(id="i2", weight=300, ef_score=0.5),
        ]
    )
    score.compute_ratios(recipe_metrics)
    assert recipe_metrics.metrics[0].ratio == pytest.approx(100 / 400)
    assert recipe_metrics.metrics[1].ratio == pytest.approx(300 / 400)


def test_compute_ratios_missing_keeps_none_ratio():
    """A missing ingredient keeps a None ratio"""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=0.3),
            IngredientMetrics(id="i2", weight=50, ef_score=None, missing=True),
        ]
    )
    score.compute_ratios(recipe_metrics)
    # scorable denominator = 100 (water excluded)
    assert recipe_metrics.metrics[0].ratio == pytest.approx(1.0)
    assert recipe_metrics.metrics[1].ratio is None


def test_compute_ratios_zero_denominator_leaves_none():
    """When no ingredient is scorable, ratios stay None."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=None, missing=True),
        ]
    )
    score.compute_ratios(recipe_metrics)
    assert recipe_metrics.metrics[0].ratio is None


# --- compute_ratios (total denominator) -------------------------------------


def test_compute_ratios_total_denominator_dilutes():
    """With the total denominator, missing ingredients dilute the ratios.

    apple 100g (ef 0.3), water 100g (missing) -> denominator 200.
    apple ratio = 0.5, contribution = 0.15 -> recipe ef = 0.15 (diluted from 0.3).
    """
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=0.3),
            IngredientMetrics(id="i2", weight=100, ef_score=None, missing=True),
        ]
    )
    score.compute_ratios(recipe_metrics, ratio_mode=AccountedWeights.ALL_WEIGHTS)
    assert recipe_metrics.metrics[0].ratio == pytest.approx(100 / 200)
    assert recipe_metrics.metrics[1].ratio is None


# --- ponderated_ef_sum ------------------------------------------------------


def test_ponderated_sum_sums_contributions():
    """The ponderated sum is the sum of per-ingredient contributions."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=0.3, ratio=0.25),
            IngredientMetrics(id="i2", weight=300, ef_score=0.5, ratio=0.75),
        ]
    )
    assert score.ponderated_ef_sum(recipe_metrics) == pytest.approx(0.45)


def test_ponderated_sum_returns_none_when_all_missing():
    """No contribution yields None."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, ef_score=None, missing=True),
        ]
    )
    assert score.ponderated_ef_sum(recipe_metrics) is None


# --- compute_green_score with accounted_weights ------------------------------


@pytest.mark.asyncio
async def test_recipe_ef_score_total_denominator_dilutes(agribalyse_index):
    """With the total denominator, missing ingredients dilute the EF score.

    apple 100g (0.3), water 100g (missing) -> scorable ef = 0.3, total ef = 0.15.
    """
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:water": create_taxonomy_node("en:water", properties={}),
        }
    )
    recipe = [
        build_ingredient_obj("i_apple", "apple", "en:apple", weight=100),
        build_ingredient_obj("i_water", "water", "en:water", weight=100),
    ]
    with patch_ingredients_taxonomy(taxonomy):
        response_scorable = await score.compute_green_score(
            recipe,
            accounted_weights=AccountedWeights.ONLY_SCORABLE,
            country="FR",
        )
        response_total = await score.compute_green_score(
            recipe,
            accounted_weights=AccountedWeights.ALL_WEIGHTS,
            country="FR",
        )
    # raw EF scores: scorable = 0.3 (only apple), total = 0.15 (apple diluted by water)
    assert response_scorable.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3) + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )
    assert response_total.numeric_score == pytest.approx(
        score.normalize_ef_score(0.15) + WORLD_EPI_MODIFIER * 0.5 + DEFAULT_DISTANCE_MODIFIER * 0.5
    )
    assert response_scorable.missing_ingredient_ids == ["i_water"]
    assert response_total.missing_ingredient_ids == ["i_water"]
