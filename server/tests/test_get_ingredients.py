from unittest.mock import patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openfoodfacts import taxonomy as off_taxonomy

from api.api import app
from api import recipes
from api import types

from tests.helpers import patch_language_check


client = TestClient(app)


INGREDIENTS_JSON_PATH = Path(__file__).parent / "inputs" / "ingredients.full.json"


@pytest.fixture
def mock_ingredients_taxonomy():
    """Load the ingredients taxonomy from the test input file via get_taxonomy"""
    ingredients_taxonomy = off_taxonomy.Taxonomy.from_path(INGREDIENTS_JSON_PATH)
    with (
        patch("openfoodfacts.taxonomy.get_taxonomy", return_value=ingredients_taxonomy),
        patch_language_check(),
    ):
        yield


def ingredient_list_to_dict(ingredients: list[types.Ingredient]) -> dict[str, str]:
    """Convert a list of Ingredient objects to a dictionary for easier comparison"""
    return {ingredient.id: ingredient.label for ingredient in ingredients}


# Total number of ingredient nodes defined in the test taxonomy
# (nodes parsed by Taxonomy.from_path from ingredients.full.json)
INGREDIENTS_TOTAL_COUNT = 20


@pytest.mark.asyncio
async def test_get_ingredients_returns_all_ingredients(mock_ingredients_taxonomy):
    """Test that get_ingredients returns every ingredient of the taxonomy,
    without any filtering."""
    result = await recipes.get_ingredients("en")
    assert isinstance(result, list)
    assert all(isinstance(ingredient, types.Ingredient) for ingredient in result)
    ingredient_ids = {ingredient.id for ingredient in result}

    # Ingredients with an Agribalyse food code are still present
    assert "en:conference-pear" in ingredient_ids
    assert "en:dry-white-wine" in ingredient_ids

    # Ingredients without an Agribalyse code are also returned (no filtering)
    assert "en:water" in ingredient_ids
    assert "en:wine" in ingredient_ids  # parent of red-wine, kept as well

    # Children hierarchy is kept too
    assert "en:raw-pear" in ingredient_ids  # child of en:pear
    assert "en:organic-red-wine" in ingredient_ids  # child of en:red-wine

    # All ingredients of the taxonomy are returned
    assert len(ingredient_ids) == INGREDIENTS_TOTAL_COUNT


@pytest.mark.asyncio
async def test_get_ingredients_includes_full_hierarchy(mock_ingredients_taxonomy):
    """Test that get_ingredients keeps the full children hierarchy (children
    of children), not only direct children."""
    result = await recipes.get_ingredients("en")
    ingredient_ids = {ingredient.id for ingredient in result}

    # en:nectarine -> en:raw-nectarine -> en:raw-nectarine-pulp-and-skin
    # raw-nectarine-pulp-and-skin is a grandchild, so it must be kept
    assert "en:raw-nectarine-pulp-and-skin" in ingredient_ids


@pytest.mark.asyncio
async def test_get_ingredients_uses_correct_language_labels(mock_ingredients_taxonomy):
    """Test that get_ingredients returns ingredients in requested language"""
    result_en = await recipes.get_ingredients("en")
    result_fr = await recipes.get_ingredients("fr")
    en_ingredients = ingredient_list_to_dict(result_en)
    fr_ingredients = ingredient_list_to_dict(result_fr)
    assert en_ingredients["en:red-wine"] == "red wine"
    assert en_ingredients["en:white-wine"] == "white wine"
    assert en_ingredients["en:nectarine"] == "nectarine"
    assert fr_ingredients["en:red-wine"] == "vin rouge"
    assert fr_ingredients["en:nectarine"] == "nectarine"


@pytest.mark.asyncio
async def test_get_ingredients_handles_language_code_with_region(
    mock_ingredients_taxonomy,
):
    """Test that get_ingredients strips region from language code (e.g. fr-FR -> fr)"""
    result_fr = await recipes.get_ingredients("fr")
    result_frFR = await recipes.get_ingredients("fr_FR")
    assert ingredient_list_to_dict(result_fr) == ingredient_list_to_dict(result_frFR)


def test_get_ingredients_api_cache_control_header(mock_ingredients_taxonomy):
    """Test that /v1/ingredients returns Cache-Control header for 1 day"""
    response = client.get("/v1/ingredients", params={"lang": "en"})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400"


@pytest.mark.asyncio
async def test_get_ingredients_excludes_synonyms_by_default(mock_ingredients_taxonomy):
    """Test that get_ingredients does not populate synonyms when include_synonyms is False"""
    result = await recipes.get_ingredients("en")
    assert all(ingredient.synonyms is None for ingredient in result)


@pytest.mark.asyncio
async def test_get_ingredients_includes_synonyms_when_requested(mock_ingredients_taxonomy):
    """Test that get_ingredients populates synonyms in the requested language"""
    result = await recipes.get_ingredients("en", include_synonyms=True)
    synonyms_by_id = {ingredient.id: ingredient.synonyms for ingredient in result}
    # en:alcohol has english synonyms 'alcohol' and 'Pure alcohol'
    assert synonyms_by_id["en:alcohol"] == ["alcohol", "Pure alcohol"]


@pytest.mark.asyncio
async def test_get_ingredients_synonyms_language_fallback(mock_ingredients_taxonomy):
    """Test that synonyms are returned in the requested language when available"""
    result_fr = await recipes.get_ingredients("fr", include_synonyms=True)
    synonyms_by_id = {ingredient.id: ingredient.synonyms for ingredient in result_fr}
    # fr synonyms of en:alcohol
    assert synonyms_by_id["en:alcohol"] == ["alcool", "Alcool pur"]


def test_get_ingredients_api_synonyms_excluded_by_default(mock_ingredients_taxonomy):
    """Test that /v1/ingredients omits the synonyms field by default"""
    response = client.get("/v1/ingredients", params={"lang": "en"})
    assert response.status_code == 200
    for ingredient in response.json()["ingredients"]:
        assert "synonyms" not in ingredient


def test_get_ingredients_api_returns_synonyms_when_requested(mock_ingredients_taxonomy):
    """Test that /v1/ingredients includes synonyms when include_synonyms=true"""
    response = client.get("/v1/ingredients", params={"lang": "en", "include_synonyms": "true"})
    assert response.status_code == 200
    synonyms_by_id = {
        ingredient["id"]: ingredient["synonyms"] for ingredient in response.json()["ingredients"]
    }
    assert synonyms_by_id["en:alcohol"] == ["alcohol", "Pure alcohol"]


def test_get_ingredients_api_invalid_language_returns_422(mock_ingredients_taxonomy):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    response = client.get("/v1/ingredients", params={"lang": "zz"})
    assert response.status_code == 422
