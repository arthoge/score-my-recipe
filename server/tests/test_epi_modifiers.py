"""Tests for the EPI modifiers computation added to the green-score.

Covers ``get_epi_modifiers``, ``gather_epi_modifiers``, ``global_epi_modifier``
and the integration of these modifiers in ``compute_green_score``.
"""

import csv
import io
from unittest.mock import patch

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
    patch_origins_taxonomy,
    patch_epi_modifiers,
)


# Sample EPI modifiers used across the tests. ``en:world`` mirrors the real
# data file (worst case, -3.0); the others are arbitrary but realistic.
FRANCE_EPI_MODIFIER = 3.0
GERMANY_EPI_MODIFIER = 2.0
ARGENTINA_EPI_MODIFIER = -2.0
ARGENTINA_DISTANCE_MODIFIER = -7.0
SAMPLE_EPI_MODIFIERS = {
    "en:world": WORLD_EPI_MODIFIER,
    "en:france": FRANCE_EPI_MODIFIER,
    "en:germany": GERMANY_EPI_MODIFIER,
    "en:argentina": ARGENTINA_EPI_MODIFIER,
}


def _raw_csv_origins() -> set[str]:
    """Return the set of origin ids present in the real EPI bonuses CSV."""
    fpath = score_data.settings.get_settings().data_dir / "greenscore-epi-bonuses.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    return {row["origin"].strip() for row in reader if row["origin"].strip()}


# --- get_epi_modifiers -----------------------------------------------------


@pytest.mark.asyncio
async def test_get_epi_modifiers_loads_real_csv():
    """The real data file is loaded into a origin -> bonus mapping."""
    modifiers = await score_data.get_epi_modifiers()
    # ``en:world`` is the worst case fallback, always present in the data file
    assert modifiers["en:world"] == WORLD_EPI_MODIFIER
    # at least one country with a positive bonus exists (e.g. France)
    assert any(v > 0 for v in modifiers.values())
    # all bonuses are numbers
    assert all(isinstance(v, float) for v in modifiers.values())


@pytest.mark.asyncio
async def test_get_epi_modifiers_contains_children_entries():
    """Origins from the CSV are expanded with their taxonomy children.

    Each child inherits its parent's bonus (worst case when several parents
    apply). For instance ``en:nova-scotia`` and ``en:quebec`` are children of
    ``en:canada`` (bonus 1) in the real origins taxonomy, so they must be
    present with the same bonus.
    """
    modifiers = await score_data.get_epi_modifiers()
    # the result holds strictly more entries than the raw CSV origins,
    # because children are added on top of the file entries
    raw_origins = _raw_csv_origins()
    assert len(modifiers) > len(raw_origins)
    # known children of en:canada (bonus 1.0) must be present and inherit it
    assert "en:canada" in modifiers
    assert modifiers["en:canada"] == 1.0
    assert modifiers["en:nova-scotia"] == 1.0
    assert modifiers["en:quebec"] == 1.0
    # every raw CSV origin is still present (children are additions, not replacements)
    assert raw_origins <= set(modifiers.keys())


@pytest.mark.asyncio
async def test_get_epi_modifiers_children_take_worst_parent(agribalyse_index, tmp_path):
    """A child shared by several parents keeps the worst (lowest) modifier.

    Builds a tiny origins taxonomy where ``en:child`` has two parents:
    ``en:parent-good`` (+2) and ``en:parent-bad`` (-2). The child must end up
    with the worst modifier (-2).
    """
    child = create_taxonomy_node("en:child")
    good_parent = create_taxonomy_node("en:parent-good", children=[child])
    bad_parent = create_taxonomy_node("en:parent-bad", children=[child])
    origins_taxonomy = create_taxonomy([good_parent, bad_parent, child])
    # only the parents are in the CSV; the child must be inferred
    csv_path = tmp_path / "greenscore-epi-bonuses.csv"
    csv_path.write_text(
        "original_name\tbonus\torigin\nGood\t2\ten:parent-good\nBad\t-2\ten:parent-bad\n",
        encoding="utf-8",
    )
    with (
        patch.object(score_data.settings, "get_settings") as mock_settings,
        patch_origins_taxonomy(origins_taxonomy),
    ):
        mock_settings.return_value.data_dir = tmp_path
        score_data.get_epi_modifiers.cache_clear()
        modifiers = await score_data.get_epi_modifiers()
    assert modifiers["en:parent-good"] == 2.0
    assert modifiers["en:parent-bad"] == -2.0
    assert modifiers["en:child"] == -2.0


@pytest.mark.asyncio
async def test_get_epi_modifiers_is_cached():
    """The modifiers table is computed once and cached for subsequent calls."""
    score_data.get_epi_modifiers.cache_clear()
    first = await score_data.get_epi_modifiers()
    second = await score_data.get_epi_modifiers()
    assert first is second


# --- gather_epi_modifiers --------------------------------------------------


@pytest.mark.asyncio
async def test_gather_epi_modifiers_no_origin_defaults_to_world(agribalyse_index):
    """An ingredient without an origin falls back to the world modifier."""
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]  # no origin
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].epi_modifier == WORLD_EPI_MODIFIER
    assert any("no origin provided" in n for n in (recipe_metrics.metrics[0].notes or []))


@pytest.mark.asyncio
async def test_gather_epi_modifiers_known_origin(agribalyse_index):
    """An ingredient with a known origin gets that origin's modifier."""
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].epi_modifier == FRANCE_EPI_MODIFIER
    assert recipe_metrics.metrics[0].notes is None


@pytest.mark.asyncio
async def test_gather_epi_modifiers_unknown_origin_defaults_to_world(agribalyse_index):
    """An origin absent from the EPI table falls back to the world modifier."""
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:unknown-origin")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].epi_modifier == WORLD_EPI_MODIFIER
    assert any("not found" in n for n in (recipe_metrics.metrics[0].notes or []))


@pytest.mark.asyncio
async def test_gather_epi_modifiers_skips_missing_ingredient(agribalyse_index):
    """A missing ingredient is skipped (no modifier, no note)."""
    ingredients_taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water")})
    recipe = [build_ingredient_obj("i1", "water", "en:water", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    assert recipe_metrics.metrics[0].epi_modifier is None
    assert recipe_metrics.metrics[0].missing is True
    assert recipe_metrics.metrics[0].notes is None


# --- global_epi_modifier ---------------------------------------------------


def test_global_epi_modifier_weighted_average():
    """The global modifier is the ratio-weighted average of per-ingredient modifiers."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, epi_modifier=FRANCE_EPI_MODIFIER, ratio=0.25),
            IngredientMetrics(id="i2", weight=300, epi_modifier=ARGENTINA_EPI_MODIFIER, ratio=0.75),
        ]
    )
    assert score.global_epi_modifier(recipe_metrics) == pytest.approx(
        FRANCE_EPI_MODIFIER * 0.25 + ARGENTINA_EPI_MODIFIER * 0.75
    )


def test_global_epi_modifier_none_when_no_modifiers():
    """With no modifier at all, the global modifier is None."""
    recipe_metrics = RecipeMetrics(
        metrics=[IngredientMetrics(id="i1", weight=100, epi_modifier=None, ratio=1.0)]
    )
    assert score.global_epi_modifier(recipe_metrics) is None


def test_global_epi_modifier_ignores_missing_ratio():
    """Ingredients without a ratio (missing) don't contribute."""
    recipe_metrics = RecipeMetrics(
        metrics=[
            IngredientMetrics(id="i1", weight=100, epi_modifier=FRANCE_EPI_MODIFIER, ratio=0.5),
            IngredientMetrics(id="i2", weight=100, epi_modifier=ARGENTINA_EPI_MODIFIER, ratio=None),
        ]
    )
    assert score.global_epi_modifier(recipe_metrics) == pytest.approx(FRANCE_EPI_MODIFIER * 0.5)


# --- compute_green_score integration --------------------------------------


@pytest.mark.asyncio
async def test_compute_green_score_applies_epi_modifier(agribalyse_index):
    """A known origin modifier is added to the numeric score.

    apple alone (ef 0.3) -> normalized ~76.38. With a France origin (modifier +3),
    numeric = 76.38 + 0 (labels) + 3 = 79.38.
    """
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    expected_ef = 0.3
    assert result.global_ef_score == pytest.approx(expected_ef)
    assert result.epi_modifier == pytest.approx(FRANCE_EPI_MODIFIER)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + FRANCE_EPI_MODIFIER + FRANCE_DISTANCE_MODIFIER
    )


@pytest.mark.asyncio
async def test_compute_green_score_no_origin_uses_world(agribalyse_index):
    """Without an origin, the world modifier (-3) is applied to the score."""
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [build_ingredient_obj("i1", "apple", "en:apple")]  # no origin
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.epi_modifier == pytest.approx(WORLD_EPI_MODIFIER)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(0.3) + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER
    )


@pytest.mark.asyncio
async def test_compute_green_score_all_missing_epi_modifier_none(agribalyse_index):
    """When no ingredient is scorable, epi_modifier is None (not 0)."""
    labels_taxonomy = create_taxonomy({})
    ingredients_taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water")})
    recipe = [build_ingredient_obj("i1", "water", "en:water", origin="en:france")]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.global_ef_score is None
    assert result.epi_modifier is None
    assert result.numeric_score is None
    assert result.missing_ingredient_ids == ["i1"]


@pytest.mark.asyncio
async def test_compute_green_score_epi_weighted_by_ratio(agribalyse_index):
    """The global EPI modifier is weighted by each ingredient's scorable ratio.

    apple 100g (France, +3) + pear 300g (Argentina, -2). Both scorable.
    global modifier = (3 * 0.25) + (-2 * 0.75) = 0.75 - 1.5 = -0.75
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
        result = await score.compute_green_score(recipe, country="FR")
    # ratios: apple 0.25, pear 0.75
    expected_epi = FRANCE_EPI_MODIFIER * 0.25 + ARGENTINA_EPI_MODIFIER * 0.75
    assert result.epi_modifier == pytest.approx(expected_epi)
    # numeric = normalized weighted ef + 0 (labels) + epi
    expected_ef = 0.3 * 0.25 + 0.5 * 0.75
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef)
        + expected_epi
        + FRANCE_DISTANCE_MODIFIER * 0.25
        + ARGENTINA_DISTANCE_MODIFIER * 0.75
    )


# --- EPI / label bonus non-cumulative rule ----------------------------------


@pytest.mark.asyncio
async def test_gather_epi_modifiers_suppressed_by_label_bonus(agribalyse_index):
    """An ingredient with an applied label bonus gets no EPI modifier.

    The ingredient has a France origin (which would normally yield +3), but it
    also carries an eu-organic label (bonus 15): the EPI pass leaves
    ``epi_modifier`` as None and records an explanatory note.
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [
        build_ingredient_obj(
            "i1", "apple", "en:apple", labels=["en:eu-organic"], origin="en:france"
        )
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        # gather_labels_bonus must run before the EPI pass: it sets labels_bonus,
        # which the EPI pass reads to decide whether to suppress the modifier.
        await score.gather_labels_bonus(recipe, recipe_metrics)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    metric = recipe_metrics.metrics[0]
    assert metric.labels_bonus == 15
    assert metric.epi_modifier is None
    assert any("label bonus" in n for n in (metric.notes or []))


@pytest.mark.asyncio
async def test_gather_epi_modifiers_applied_when_label_grants_no_bonus(agribalyse_index):
    """A label that grants no bonus does not suppress the EPI modifier.

    Label Rouge is restricted to some meats; on an apple it is filtered out and
    grants no bonus (labels_bonus stays None), so the EPI modifier still applies.
    This pins the suppression trigger to an *applied* bonus, not a bare label tag.
    """
    labels_taxonomy = create_taxonomy({"fr:label-rouge": create_taxonomy_node("fr:label-rouge")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [
        build_ingredient_obj(
            "i1", "apple", "en:apple", labels=["fr:label-rouge"], origin="en:france"
        )
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        recipe_metrics = await score.gather_ef_metrics(recipe)
        score.compute_ratios(recipe_metrics)
        await score.gather_labels_bonus(recipe, recipe_metrics)
        await score.gather_epi_modifiers(recipe, recipe_metrics)
    metric = recipe_metrics.metrics[0]
    # Label Rouge does not apply to apple: no bonus, so EPI is not suppressed.
    assert metric.labels_bonus is None
    assert metric.epi_modifier == FRANCE_EPI_MODIFIER


@pytest.mark.asyncio
async def test_compute_green_score_epi_suppressed_by_label_bonus(agribalyse_index):
    """A label bonus suppresses the EPI modifier but not the label or distance.

    apple (France, eu-organic bonus 15): the France EPI modifier (+3) is not
    applied, so epi_modifier is None. The label bonus (+15) and the distance
    modifier (France -> France, +3) still apply.
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
    ingredients_taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    recipe = [
        build_ingredient_obj(
            "i1", "apple", "en:apple", labels=["en:eu-organic"], origin="en:france"
        )
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    expected_ef = 0.3
    assert result.labels_bonus == pytest.approx(15)
    # EPI is suppressed by the label bonus.
    assert result.epi_modifier is None
    # The distance modifier is a separate axis and is unaffected.
    assert result.distances_modifier == pytest.approx(FRANCE_DISTANCE_MODIFIER)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + 15 + FRANCE_DISTANCE_MODIFIER
    )


@pytest.mark.asyncio
async def test_compute_green_score_epi_suppressed_per_ingredient(agribalyse_index):
    """EPI is suppressed only for labeled ingredients, without renormalization.

    apple 100g (France, eu-organic) + pear 300g (Argentina, no label).
    ratios: apple 0.25, pear 0.75.
    - labels_bonus = 15 * 0.25 = 3.75  (only apple is labeled)
    - epi = ARGENTINA * 0.75 = -1.5    (apple suppressed; ratios NOT renormalized)
    - distance = France*0.25 + Argentina*0.75 = 0.75 - 5.25 = -4.5
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
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
        build_ingredient_obj(
            "i_apple", "apple", "en:apple", weight=100,
            labels=["en:eu-organic"], origin="en:france",
        ),
        build_ingredient_obj(
            "i_pear", "pear", "en:pear", weight=300, origin="en:argentina",
        ),
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    expected_ef = 0.3 * 0.25 + 0.5 * 0.75
    expected_labels = 15 * 0.25
    expected_epi = ARGENTINA_EPI_MODIFIER * 0.75
    expected_distance = FRANCE_DISTANCE_MODIFIER * 0.25 + ARGENTINA_DISTANCE_MODIFIER * 0.75
    assert result.labels_bonus == pytest.approx(expected_labels)
    assert result.epi_modifier == pytest.approx(expected_epi)
    assert result.distances_modifier == pytest.approx(expected_distance)
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef)
        + expected_labels
        + expected_epi
        + expected_distance
    )


@pytest.mark.asyncio
async def test_compute_green_score_all_labeled_epi_none(agribalyse_index):
    """When every scorable ingredient has a label bonus, epi_modifier is None.

    apple (France, eu-organic) + pear (Argentina, eu-organic): both labeled, so
    no ingredient contributes to EPI and the global epi_modifier is None
    (treated as 0.0 in the final additive sum).
    """
    labels_taxonomy = create_taxonomy({"en:eu-organic": create_taxonomy_node("en:eu-organic")})
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
        build_ingredient_obj(
            "i_apple", "apple", "en:apple", weight=100,
            labels=["en:eu-organic"], origin="en:france",
        ),
        build_ingredient_obj(
            "i_pear", "pear", "en:pear", weight=300,
            labels=["en:eu-organic"], origin="en:argentina",
        ),
    ]
    with (
        patch_ingredients_taxonomy(ingredients_taxonomy),
        patch_labels_taxonomy(labels_taxonomy),
        patch_epi_modifiers(SAMPLE_EPI_MODIFIERS),
    ):
        result = await score.compute_green_score(recipe, country="FR")
    assert result.epi_modifier is None
    assert result.labels_bonus == pytest.approx(15)
    expected_ef = 0.3 * 0.25 + 0.5 * 0.75
    expected_distance = FRANCE_DISTANCE_MODIFIER * 0.25 + ARGENTINA_DISTANCE_MODIFIER * 0.75
    assert result.numeric_score == pytest.approx(
        score.normalize_ef_score(expected_ef) + 15 + expected_distance
    )
