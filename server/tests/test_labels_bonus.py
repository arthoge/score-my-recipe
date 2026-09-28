"""Tests for the labels bonus computation added to the green-score.

Covers ``safe_zip_recipe_metrics``, ``labels_bonus_full``, ``gather_labels_bonus``,
``global_labels_bonus`` and the integration of these bonuses in
``compute_green_score``.
"""

import pytest

from api.score_data import DEFAULT_DISTANCE_MODIFIER
from api import score
from api.score_types import IngredientMetrics, RecipeMetrics
from tests.helpers import (
    WORLD_EPI_MODIFIER,
    create_taxonomy,
    create_taxonomy_node,
    build_ingredient_obj,
    patch_ingredients_taxonomy,
    patch_labels_taxonomy,
)


# --- safe_zip_recipe_metrics ------------------------------------------------


def test_safe_zip_matches():
    """Zipping a recipe and metrics with matching ids yields aligned pairs."""
    recipe = [
        build_ingredient_obj("i1", "apple", "en:apple"),
        build_ingredient_obj("i2", "pear", "en:pear"),
    ]
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100),
            IngredientMetrics(id="i2", weight=100),
        ]
    )
    pairs = list(score.safe_zip_recipe_metrics(recipe, recipe_metrics))
    assert [ing.id for ing, _ in pairs] == ["i1", "i2"]
    assert [m.id for _, m in pairs] == ["i1", "i2"]


def test_safe_zip_raises_on_length_mismatch():
    """A length mismatch between recipe and metrics raises a ValueError."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100),
            IngredientMetrics(id="i2", weight=100),
        ]
    )
    with pytest.raises(ValueError, match="different lengths"):
        score.safe_zip_recipe_metrics(recipe, recipe_metrics)


def test_safe_zip_raises_on_id_mismatch():
    """A mismatched ingredient id (same length) raises a ValueError."""
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]
    recipe_metrics = RecipeMetrics(metrics=[IngredientMetrics(id="i_other", weight=100)])
    with pytest.raises(ValueError, match="different ingredient ids"):
        score.safe_zip_recipe_metrics(recipe, recipe_metrics)


# --- labels_bonus_full ------------------------------------------------------


@pytest.mark.asyncio
async def test_labels_bonus_full_includes_children():
    """Children of a listed label inherit its bonus, listed labels are present."""
    organic = create_taxonomy_node("en:eu-organic")
    # a child label that is not explicitly listed
    child = create_taxonomy_node("en:organic-child", parents=[organic])
    taxonomy = create_taxonomy(
        {
            "en:eu-organic": organic,
            "en:organic-child": child,
        }
    )
    with patch_labels_taxonomy(taxonomy):
        bonuses = await score.labels_bonus_full()
    assert bonuses["en:eu-organic"] == 15
    # child inherits the parent bonus
    assert bonuses["en:organic-child"] == 15


@pytest.mark.asyncio
async def test_labels_bonus_full_keeps_higher_explicit_bonus():
    """An explicit bonus higher than an inherited one is kept."""
    parent = create_taxonomy_node("en:eu-organic")  # 15
    # child explicitly listed with a higher bonus (20)
    child = create_taxonomy_node("en:demeter", parents=[parent])
    taxonomy = create_taxonomy({"en:eu-organic": parent, "en:demeter": child})
    with patch_labels_taxonomy(taxonomy):
        bonuses = await score.labels_bonus_full()
    assert bonuses["en:demeter"] == 20


@pytest.mark.asyncio
async def test_labels_bonus_full_warns_on_missing_label(caplog):
    """A label id absent from the taxonomy is skipped with a warning."""
    taxonomy = create_taxonomy({})
    with patch_labels_taxonomy(taxonomy):
        with caplog.at_level("WARNING", logger="api.score"):
            bonuses = await score.labels_bonus_full()
    # all listed labels are missing from the (empty) taxonomy, but the static
    # entries still appear (with their explicit bonuses)
    assert bonuses["en:eu-organic"] == 15
    assert any("not found in taxonomy" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_labels_bonus_full_is_cached():
    """The bonus table is computed once and cached for subsequent calls."""
    taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    with patch_labels_taxonomy(taxonomy) as mock_tax:
        first = await score.labels_bonus_full()
        # second call: the patched function must not be awaited again
        assert mock_tax.await_count == 1
        second = await score.labels_bonus_full()
        assert mock_tax.await_count == 1
    assert first is second


# --- gather_labels_bonus ----------------------------------------------------


@pytest.mark.asyncio
async def test_gather_labels_bonus_sets_metric_bonus(agribalyse_index):
    """An ingredient with a known label gets its bonus on the metric."""
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", labels=["en:eu-organic"])]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].labels_bonus == 15


@pytest.mark.asyncio
async def test_gather_labels_bonus_skips_missing_ingredient(agribalyse_index):
    """A missing ingredient is skipped even when it carries a label."""
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:water": create_taxonomy_node("en:water", properties={}),
        }
    )
    recipe = [
        build_ingredient_obj("i_apple", "apple", "en:apple"),
        build_ingredient_obj("i_water", "water", "en:water", labels=["en:eu-organic"]),
    ]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
    apple = next(m for m in recipe_metrics.metrics if m.id == "i_apple")
    water = next(m for m in recipe_metrics.metrics if m.id == "i_water")
    assert apple.labels_bonus is None  # no label on apple
    assert water.labels_bonus is None  # missing -> skipped


@pytest.mark.asyncio
async def test_gather_labels_bonus_unknown_label_keeps_none(agribalyse_index):
    """A label not in the bonus table leaves the metric bonus at None."""
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", labels=["en:unknown-label"])]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].labels_bonus is None


@pytest.mark.asyncio
async def test_gather_labels_bonus_takes_max_bonus(agribalyse_index):
    """When several labels match, the highest bonus is kept."""
    labels_taxonomy = create_taxonomy(
        {
            "en:eu-organic": create_taxonomy_node("en:eu-organic"),  # 15
            "en:demeter": create_taxonomy_node("en:demeter"),  # 20
        }
    )
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [
        build_ingredient_obj("i1", "apple", "en:apple", labels=["en:eu-organic", "en:demeter"])
    ]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].labels_bonus == 20


@pytest.mark.asyncio
async def test_gather_labels_bonus_ignores_ingredient_without_labels(agribalyse_index):
    """An ingredient with no labels is left untouched."""
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]  # no labels
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].labels_bonus is None


# --- global_labels_bonus ----------------------------------------------------


def test_global_labels_bonus_weighted_average():
    """The global bonus is the ratio-weighted average of per-ingredient bonuses."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, labels_bonus=20, ratio=0.25),
            IngredientMetrics(id="i2", weight=300, labels_bonus=10, ratio=0.75),
        ]
    )
    assert score.global_labels_bonus(recipe_metrics) == pytest.approx(20 * 0.25 + 10 * 0.75)


def test_global_labels_bonus_zero_when_no_bonuses():
    """With no bonus at all, the global bonus is 0.0 (not None)."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, labels_bonus=None, ratio=1.0),
        ]
    )
    assert score.global_labels_bonus(recipe_metrics) == 0.0


def test_global_labels_bonus_ignores_missing_ratio():
    """Ingredients without a ratio (missing) don't contribute."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, labels_bonus=20, ratio=0.5),
            IngredientMetrics(id="i2", weight=100, labels_bonus=15, ratio=None),
        ]
    )
    assert score.global_labels_bonus(recipe_metrics) == pytest.approx(20 * 0.5)


# --- compute_green_score integration ----------------------------------------


@pytest.mark.asyncio
async def test_compute_green_score_applies_labels_bonus(agribalyse_index):
    """A label bonus reduces the numeric score and may shift the letter grade.

    apple alone (ef 0.3) -> normalized ~76.38 (grade A). With an eu-organic
    label (bonus 15), numeric = 76.38 - 15 = 61.38 (grade B).
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", labels=["en:eu-organic"])]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        result = await score.compute_green_score(recipe, country="FR")
    expected_ef = 0.3
    assert result.global_ef_score == pytest.approx(expected_ef)
    assert result.labels_bonus == pytest.approx(15)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + 15 + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )
    assert result.letter_grade == "A"


@pytest.mark.asyncio
async def test_compute_green_score_no_label_keeps_ef_score(agribalyse_index):
    """Without any label, the labels bonus is 0 and the numeric score is unchanged."""
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        result = await score.compute_green_score(recipe, country="FR")
    expected_normalized = score.normalize_ef_score(0.3)
    assert result.labels_bonus == pytest.approx(0.0)
    assert result.numeric_score == pytest.approx(
        expected_normalized + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )
    assert result.letter_grade == "B"


@pytest.mark.asyncio
async def test_compute_green_score_all_missing_labels_bonus_none(agribalyse_index):
    """When no ingredient is scorable, labels_bonus is None (not 0)."""
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {"en:water": create_taxonomy_node("en:water", properties={})}
    )
    recipe = [build_ingredient_obj("i1", "water", "en:water", labels=["en:eu-organic"])]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.global_ef_score is None
    assert result.labels_bonus is None
    assert result.numeric_score is None
    assert result.letter_grade is None
    assert result.missing_ingredient_ids == ["i1"]


@pytest.mark.asyncio
async def test_compute_green_score_diluted_bonus(agribalyse_index):
    """The global bonus is weighted by the scorable ratio of labelled ingredients.

    apple 100g (label, bonus 15) + water 100g (missing, no contribution).
    Only apple is scorable (ratio 1.0) so the bonus stays 15.
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:water": create_taxonomy_node("en:water", properties={}),
        }
    )
    recipe = [
        build_ingredient_obj("i_apple", "apple", "en:apple", labels=["en:eu-organic"]),
        build_ingredient_obj("i_water", "water", "en:water"),
    ]
    with patch_ingredients_taxonomy(ingredients_taxonomy), patch_labels_taxonomy(labels_taxonomy):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.labels_bonus == pytest.approx(15)
    expected_normalized = score.normalize_ef_score(0.3)
    assert result.numeric_score == pytest.approx(
        expected_normalized + 15 + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )
