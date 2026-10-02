from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.api import app
from api import types
from api.types import OFFIngredient
from tests.helpers import build_mock_units_taxonomy, patch_units_taxonomy

client = TestClient(app)


@pytest.fixture
def mock_off_parse_text():
    """Mock the OpenFoodFacts API parse_text response"""
    with (
        patch("api.recipes.off.parse_text", new_callable=AsyncMock) as mock,
        patch_units_taxonomy(build_mock_units_taxonomy()),
    ):
        mock.return_value = [
            OFFIngredient(
                id="en:tomatoes",
                text="tomates",
                quantity="500g",
                quantity_g=500.0,
                ciqual_food_code="12345",
                is_in_taxonomy=1,
            ),
            OFFIngredient(
                id="en:onions",
                text="oignons",
                quantity="2 units",
                quantity_g=200.0,
                ciqual_food_code="67890",
                is_in_taxonomy=1,
            ),
        ]
        yield mock


def test_parse_text_returns_ingredients(mock_off_parse_text):
    """Test that parse_text endpoint returns parsed ingredients"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "tomates 500g, oignons 2 units", "lang": "fr"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ingredients" in data
    assert len(data["ingredients"]) == 2


def test_parse_text_ingredient_structure(mock_off_parse_text):
    """Test that parse_text returns correct ingredient structure"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "tomates 500g", "lang": "fr"},
    )
    assert response.status_code == 200
    ingredient = response.json()["ingredients"][0]
    assert "taxonomy_id" in ingredient
    assert "codified_ingredient" in ingredient
    assert "is_in_taxonomy" in ingredient
    assert "quantity_g" in ingredient
    assert "origins" in ingredient
    assert "labels" in ingredient
    assert "notes" in ingredient


def test_parse_text_converts_off_ingredient(mock_off_parse_text):
    """Test that OFFIngredient is correctly converted to RecipeIngredient"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "tomates 500g", "lang": "fr"},
    )
    assert response.status_code == 200
    ingredient = response.json()["ingredients"][0]
    assert ingredient["taxonomy_id"] == "en:tomatoes"
    assert ingredient["codified_ingredient"] == "tomates"
    assert ingredient["is_in_taxonomy"] is True
    assert ingredient["quantity_g"] == 500.0


def test_parse_text_is_in_taxonomy_conversion(mock_off_parse_text):
    """Test that is_in_taxonomy integer is converted to boolean"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "tomates 500g", "lang": "fr"},
    )
    assert response.status_code == 200
    ingredient = response.json()["ingredients"][0]
    assert ingredient["is_in_taxonomy"] is True


def test_parse_text_empty_request():
    """Test that parse_text handles empty text"""
    with patch("api.recipes.off.parse_text", new_callable=AsyncMock) as mock:
        mock.return_value = []
        response = client.post(
            "/v1/parse_text",
            json={"text": "", "lang": "fr"},
        )
        assert response.status_code == 200
        assert response.json()["ingredients"] == []


def test_parse_text_normalizes_language_code(mock_off_parse_text):
    """Test that parse_text normalizes the language code (fr-FR or fr_FR -> fr)

    This matches the behaviour of the taxonomy endpoints and is required as the
    OFF ingredient parsing API only accepts 2-letter language codes.
    """
    for lang in ("fr-FR", "fr_FR"):
        mock_off_parse_text.reset_mock()
        response = client.post(
            "/v1/parse_text",
            json={"text": "tomates 500g", "lang": lang},
        )
        assert response.status_code == 200
        mock_off_parse_text.assert_awaited_once_with("tomates 500g", "fr")


@pytest.fixture
def mock_off_parse_text_with_origins_and_labels():
    """Mock returning ingredients that have origins and labels detected"""
    with (
        patch("api.recipes.off.parse_text", new_callable=AsyncMock) as mock,
        patch_units_taxonomy(build_mock_units_taxonomy()),
    ):
        mock.return_value = [
            OFFIngredient(
                id="en:butter",
                text="butter",
                quantity="200g",
                quantity_g=200.0,
                is_in_taxonomy=1,
                origins="en:france",
                labels="en:organic",
            ),
            OFFIngredient(
                id="en:cocoa",
                text="cocoa",
                quantity="100g",
                quantity_g=100.0,
                is_in_taxonomy=1,
                origins="en:ecuador",
                labels=None,
            ),
        ]
        yield mock


def test_parse_text_returns_origins_and_labels_when_detected(
    mock_off_parse_text_with_origins_and_labels,
):
    """Test that origins and labels from OFF are passed through to the API response"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "200g French organic butter, 100g cocoa from Ecuador", "lang": "en"},
    )
    assert response.status_code == 200
    ingredients = response.json()["ingredients"]

    # First ingredient: butter — should have both origins and labels
    assert ingredients[0]["origins"] == {"id": "en:france", "label": "France", "isInTaxonomy": True}
    assert ingredients[0]["labels"] == [
        {"id": "en:organic", "label": "Organic", "isInTaxonomy": True}
    ]

    # Second ingredient: cocoa — has origin but no label
    assert ingredients[1]["origins"] == {
        "id": "en:ecuador",
        "label": "Ecuador",
        "isInTaxonomy": True,
    }
    assert ingredients[1]["labels"] == []


def test_parse_text_origins_and_labels_null_when_not_in_text(mock_off_parse_text):
    """Test that origins and labels are null (not absent) when not detected in text"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "tomates 500g, oignons", "lang": "fr"},
    )
    assert response.status_code == 200
    ingredients = response.json()["ingredients"]

    for ingredient in ingredients:
        # Fields must EXIST in the response even when null — not be missing entirely
        assert "origins" in ingredient
        assert "labels" in ingredient
        assert ingredient["labels"] == []
        assert ingredient["notes"] == []


@pytest.fixture
def mock_off_parse_text_with_multiple_values():
    """Mock returning an ingredient with comma-separated origins and labels"""
    with (
        patch("api.recipes.off.parse_text", new_callable=AsyncMock) as mock,
        patch_units_taxonomy(build_mock_units_taxonomy()),
    ):
        mock.return_value = [
            OFFIngredient(
                id="en:salad",
                text="salad",
                quantity="100g",
                quantity_g=100.0,
                is_in_taxonomy=1,
                origins="en:france,en:italy",
                labels="en:organic,en:vegan",
            )
        ]
        yield mock


def test_parse_text_handles_multiple_origins_and_labels(mock_off_parse_text_with_multiple_values):
    """Test that multiple labels are split into a list, and multiple origins are dropped with a note"""
    response = client.post(
        "/v1/parse_text",
        json={"text": "100g organic vegan salad from France and Italy", "lang": "en"},
    )
    assert response.status_code == 200
    ingredients = response.json()["ingredients"]

    # Labels should be split into a list of two items
    assert ingredients[0]["labels"] == [
        {"id": "en:organic", "label": "Organic", "isInTaxonomy": True},
        {"id": "en:vegan", "label": "Vegan", "isInTaxonomy": True},
    ]

    # Origins should be dropped (None) because there are multiple
    assert ingredients[0]["origins"] is None

    # A note should be added explaining the dropped origin
    assert len(ingredients[0]["notes"]) == 1
    assert "Dropped origins" in ingredients[0]["notes"][0]
    assert "en:france,en:italy" in ingredients[0]["notes"][0]


# ---------------------------------------------------------------------------
# quantity_unit resolution into a TaxonomyItem
# ---------------------------------------------------------------------------


def test_parse_text_resolves_known_unit_name(mock_off_parse_text):
    """A parsed unit name (e.g. 'g') resolves to a taxonomy TaxonomyItem."""
    response = client.post("/v1/parse_text", json={"text": "tomates 500g", "lang": "fr"})
    assert response.status_code == 200
    ingredient = response.json()["ingredients"][0]
    # 'g' resolves to en:gram (label localized in fr: "gramme")
    assert ingredient["quantity_unit"] == {
        "id": "en:gram",
        "label": "gramme",
        "isInTaxonomy": True,
    }
    assert ingredient["quantity_value"] == 500.0


def test_parse_text_unresolvable_unit_becomes_free_text(mock_off_parse_text):
    """A parsed unit not in the taxonomy becomes a free-text TaxonomyItem."""
    response = client.post(
        "/v1/parse_text", json={"text": "oignons 2 units", "lang": "fr"}
    )
    assert response.status_code == 200
    # The mock returns two ingredients; the second (oignons) has unit "units".
    ingredient = response.json()["ingredients"][1]
    # 'units' is not a known unit: free-text entry with id=null
    assert ingredient["quantity_unit"] == {
        "id": None,
        "label": "units",
        "isInTaxonomy": False,
    }
    assert ingredient["quantity_value"] == 2.0


@pytest.mark.asyncio
async def test_off_ingredient_to_recipe_ingredient_no_unit_returns_item():
    """An ingredient without a unit resolves to the synthetic 'item' unit."""
    from api.recipes import off_ingredient_to_recipe_ingredient

    off_ingredient = OFFIngredient(
        id="en:egg",
        text="egg",
        quantity="3",
        quantity_g=150.0,
        is_in_taxonomy=1,
    )
    with patch_units_taxonomy(build_mock_units_taxonomy()):
        ingredient = await off_ingredient_to_recipe_ingredient(off_ingredient, "en")
    assert ingredient.quantity_unit == types.TaxonomyItem(
        id="item", label="item", is_in_taxonomy=True
    )
    assert ingredient.quantity_value == 3.0


@pytest.mark.asyncio
async def test_off_ingredient_to_recipe_ingredient_none_quantity_returns_item():
    """An ingredient with quantity=None resolves to the 'item' unit."""
    from api.recipes import off_ingredient_to_recipe_ingredient

    off_ingredient = OFFIngredient(
        id="en:egg",
        text="egg",
        quantity=None,
        quantity_g=None,
        is_in_taxonomy=1,
    )
    with patch_units_taxonomy(build_mock_units_taxonomy()):
        ingredient = await off_ingredient_to_recipe_ingredient(off_ingredient, "en")
    assert ingredient.quantity_unit is not None
    assert ingredient.quantity_unit.id == "item"
    assert ingredient.quantity_value is None


@pytest.mark.asyncio
async def test_off_ingredient_to_recipe_ingredient_resolves_unit_id():
    """A unit given as a taxonomy id resolves to the matching TaxonomyItem."""
    from api.recipes import off_ingredient_to_recipe_ingredient

    off_ingredient = OFFIngredient(
        id="en:flour",
        text="flour",
        quantity="2 kg",
        quantity_g=2000.0,
        is_in_taxonomy=1,
    )
    with patch_units_taxonomy(build_mock_units_taxonomy()):
        ingredient = await off_ingredient_to_recipe_ingredient(off_ingredient, "en")
    # 'kg' resolves to en:kilogram via the 'xx' name
    assert ingredient.quantity_unit == types.TaxonomyItem(
        id="en:kilogram", label="kilogram", is_in_taxonomy=True
    )
    assert ingredient.quantity_value == 2.0


@pytest.mark.asyncio
async def test_off_ingredient_to_recipe_ingredient_resolves_synonym():
    """A unit given as a synonym (e.g. 'tasse') resolves to its TaxonomyItem."""
    from api.recipes import off_ingredient_to_recipe_ingredient

    off_ingredient = OFFIngredient(
        id="en:flour",
        text="flour",
        quantity="1 tasse",
        quantity_g=120.0,
        is_in_taxonomy=1,
    )
    with patch_units_taxonomy(build_mock_units_taxonomy()):
        ingredient = await off_ingredient_to_recipe_ingredient(off_ingredient, "fr")
    # 'tasse' is the fr label of en:cup
    assert ingredient.quantity_unit == types.TaxonomyItem(
        id="en:cup", label="tasse", is_in_taxonomy=True
    )
