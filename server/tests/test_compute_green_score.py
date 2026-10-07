"""Tests for ``score.compute_green_score`` (end-to-end green-score computation)."""

import pytest

from api.score_data import DEFAULT_DISTANCE_MODIFIER
from api import score
from api import types
from tests.helpers import (
    WORLD_EPI_MODIFIER,
    create_taxonomy,
    create_taxonomy_node,
    build_ingredient_obj,
    patch_ingredients_taxonomy,
)


@pytest.mark.asyncio
async def test_score_for_single_ingredient(agribalyse_index):
    """An apple (ef_score 0.3) yields the normalized score and matching letter."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.compute_green_score(
            types.GreenScoreRequest(
                ingredients=[build_ingredient_obj("i1", "apple", "en:apple")]
            ).ingredients,
            country="FR",
        )
    assert result.numeric_score == pytest.approx(
        76.381296 + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER, rel=1e-4
    )
    assert result.letter_grade == "B"
    assert result.missing_ingredient_ids == []


@pytest.mark.asyncio
async def test_score_weighted_mix(agribalyse_index):
    """A mix of apple (100g) and pear (300g) -> ef 0.45 -> grade C."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:pear": create_taxonomy_node(
                "en:pear", properties={"agribalyse_food_code": {"en": "10002"}}
            ),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.compute_green_score(
            types.GreenScoreRequest(
                ingredients=[
                    build_ingredient_obj("i1", "apple", "en:apple", weight=100),
                    build_ingredient_obj("i2", "pear", "en:pear", weight=300),
                ]
            ).ingredients,
            country="FR",
        )
    assert result.numeric_score == pytest.approx(
        57.813704 + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER, rel=1e-4
    )
    assert result.letter_grade == "C"
    assert result.missing_ingredient_ids == []


@pytest.mark.asyncio
async def test_missing_ingredients_reported(agribalyse_index):
    """Ingredients without an Agribalyse row are listed, the rest is scored."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            ),
            "en:water": create_taxonomy_node("en:water", properties={}),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.compute_green_score(
            types.GreenScoreRequest(
                ingredients=[
                    build_ingredient_obj("i_apple", "apple", "en:apple"),
                    build_ingredient_obj("i_water", "water", "en:water"),
                ]
            ).ingredients,
            country="FR",
        )
    assert result.numeric_score == pytest.approx(
        76.381296 + WORLD_EPI_MODIFIER + DEFAULT_DISTANCE_MODIFIER, rel=1e-4
    )
    assert result.letter_grade == "B"
    assert result.missing_ingredient_ids == ["i_water"]


@pytest.mark.asyncio
async def test_no_score_when_all_missing(agribalyse_index):
    """With no scorable ingredient the score and letter are null."""
    taxonomy = create_taxonomy({"en:water": create_taxonomy_node("en:water", properties={})})
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.compute_green_score(
            types.GreenScoreRequest(
                ingredients=[build_ingredient_obj("i1", "water", "en:water")]
            ).ingredients,
            country="FR",
        )
    assert result.numeric_score is None
    assert result.letter_grade is None
    assert result.missing_ingredient_ids == ["i1"]


@pytest.mark.asyncio
async def test_free_text_codified_ingredient_is_missing(agribalyse_index):
    """A codified ingredient with a null id is accepted and reported as missing.

    This mirrors an ingredient whose value was edited in the UI without
    selecting a suggestion: the frontend (see ``Tags.svelte`` edit flow) resets
    the id to null so the ingredient is no longer matched against the
    previously selected taxonomy node. Even when the taxonomy contains a node
    with the same label, no Agribalyse row is matched and the ingredient is
    flagged as missing instead of being scored against the old entry.
    """
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.compute_green_score(
            types.GreenScoreRequest(
                ingredients=[build_ingredient_obj("i1", "apple", taxonomy_id=None)]
            ).ingredients,
            country="FR",
        )
    assert result.numeric_score is None
    assert result.letter_grade is None
    assert result.missing_ingredient_ids == ["i1"]


@pytest.mark.asyncio
async def test_zero_quantity_is_excluded_from_green_score(agribalyse_index):
    """Zero-weight matches are excluded and do not change the score for the remaining food."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    positive = build_ingredient_obj("positive", "apple", "en:apple")
    zero = build_ingredient_obj("zero", "apple", "en:apple")
    zero.weight = 0
    with patch_ingredients_taxonomy(taxonomy):
        complete = await score.compute_green_score([positive])
        partial = await score.compute_green_score([positive, zero])
        empty = await score.compute_green_score([zero])
    assert partial.numeric_score == complete.numeric_score
    assert partial.letter_grade == complete.letter_grade
    assert partial.missing_ingredient_ids == ["zero"]
    assert empty.letter_grade is None
    assert empty.numeric_score is None


@pytest.mark.asyncio
async def test_missing_name_draft_is_excluded_from_green_score(agribalyse_index):
    """A quantity-only draft cannot contribute even if a taxonomy reference is present."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    positive = build_ingredient_obj("positive", "apple", "en:apple")
    draft = build_ingredient_obj("draft", "", "en:apple")
    with patch_ingredients_taxonomy(taxonomy):
        complete = await score.compute_green_score([positive])
        partial = await score.compute_green_score([positive, draft])
    assert partial.numeric_score == complete.numeric_score
    assert partial.missing_ingredient_ids == ["draft"]
