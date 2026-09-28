from unittest.mock import patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openfoodfacts import taxonomy as off_taxonomy

from api.api import app
from api import agribalyse
from api import recipes
from api import types

from tests.helpers import patch_language_check


client = TestClient(app)


INGREDIENTS_JSON_PATH = Path(__file__).parent / "inputs" / "ingredients.full.json"


@pytest.fixture
def mock_ingredients_taxonomy():
    """Load the test ingredients taxonomy and a matching Agribalyse index.

    The Agribalyse index is tailored to the test taxonomy so that
    ``find_agribalyse_row`` resolves deterministically without loading the
    real (committed) Agribalyse CSV. Rows are keyed by the very codes the test
    taxonomy declares: a ``score`` is set for the scorable cases, and
    intentionally left unset for ``en:water`` (ciqual 18066) to exercise the
    "matched row without a score" branch of ``has_ef_score``.
    """
    ingredients_taxonomy = off_taxonomy.Taxonomy.from_path(INGREDIENTS_JSON_PATH)

    # Rows indexed by Agribalyse code (``agribalyse_*`` taxonomy properties).
    by_code = {
        # en:dry-white-wine / en:white-wine (agribalyse[_proxy]_food_code 5215)
        "5215": {"code": "5215", "ciqual_code": "5215", "name_fr": "Dry white wine", "score": 0.4},
        # en:red-wine (agribalyse_food_code 5214); inherited by en:organic-red-wine
        "5214": {"code": "5214", "ciqual_code": "5214", "name_fr": "Red wine", "score": 0.5},
        # en:pear (agribalyse_proxy_food_code 13037); inherited by en:raw-pear
        "13037": {"code": "13037", "ciqual_code": "13037", "name_fr": "Pear", "score": 0.2},
        # en:conference-pear (agribalyse_proxy_food_code 13188)
        "13188": {"code": "13188", "ciqual_code": "13188", "name_fr": "Conference pear", "score": 0.25},
    }
    # Rows indexed by Ciqual code (``ciqual_*`` taxonomy properties).
    by_ciqual = {
        "5215": by_code["5215"],
        "5214": by_code["5214"],
        "13037": by_code["13037"],
        "13188": by_code["13188"],
        # en:alcohol (ciqual_food_code 1014); inherited by en:wine
        "1014": {"code": "91014", "ciqual_code": "1014", "name_fr": "Alcohol", "score": 0.6},
        # en:water (ciqual_food_code 18066): row exists but has NO score ->
        # has_ef_score must be False (mirrors green-score "missing" logic).
        "18066": {"code": "18066", "ciqual_code": "18066", "name_fr": "Water"},
    }
    saved = (agribalyse._agribalyse_by_code, agribalyse._agribalyse_by_ciqual)
    agribalyse._agribalyse_by_code = by_code
    agribalyse._agribalyse_by_ciqual = by_ciqual
    # The entries are cached per language; clear so each test rebuilds them
    # against the (possibly re-bound) Agribalyse index.
    recipes._get_ingredients_entries.cache_clear()
    try:
        with (
            patch("openfoodfacts.taxonomy.get_taxonomy", return_value=ingredients_taxonomy),
            patch_language_check(),
        ):
            yield
    finally:
        agribalyse._agribalyse_by_code, agribalyse._agribalyse_by_ciqual = saved
        recipes._get_ingredients_entries.cache_clear()


def ingredient_list_to_dict(ingredients: list[types.SuggestedIngredient]) -> dict[str, str]:
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


@pytest.mark.asyncio
async def test_get_ingredients_has_ef_score_true_for_scored_ingredients(mock_ingredients_taxonomy):
    """Ingredients resolving to an Agribalyse row with a score report has_ef_score=True."""
    result = await recipes.get_ingredients("en")
    has_ef = {ingredient.id: ingredient.has_ef_score for ingredient in result}

    # Matched through the agribalyse_food_code property (own code, agribalyse column).
    assert has_ef["en:dry-white-wine"] is True
    # Matched through the ciqual_food_code property (own code, ciqual column).
    assert has_ef["en:alcohol"] is True
    # Matched through the agribalyse_proxy_food_code property (own code).
    assert has_ef["en:conference-pear"] is True
    # Inherited from a parent's code (search_parents=True, like the green-score).
    assert has_ef["en:raw-pear"] is True  # inherits en:pear code
    assert has_ef["en:wine"] is True  # inherits en:alcohol code


@pytest.mark.asyncio
async def test_get_ingredients_has_ef_score_false_for_unscored(mock_ingredients_taxonomy):
    """Ingredients with no scorable Agribalyse row report has_ef_score=False."""
    result = await recipes.get_ingredients("en")
    has_ef = {ingredient.id: ingredient.has_ef_score for ingredient in result}

    # A matching Agribalyse row but without a score is NOT scorable
    # (mirrors the green-score "missing" logic in gather_ef_metrics).
    assert has_ef["en:water"] is False
    # No code property at all, and none on parents.
    assert has_ef["en:fruit"] is False
    # A code that is not present in the Agribalyse index.
    assert has_ef["en:nectarine"] is False


def test_get_ingredients_api_returns_has_ef_score(mock_ingredients_taxonomy):
    """The /v1/ingredients endpoint exposes has_ef_score for each ingredient."""
    response = client.get("/v1/ingredients", params={"lang": "en"})
    assert response.status_code == 200
    by_id = {ingredient["id"]: ingredient for ingredient in response.json()["ingredients"]}
    assert by_id["en:dry-white-wine"]["has_ef_score"] is True
    assert by_id["en:water"]["has_ef_score"] is False
