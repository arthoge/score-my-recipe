"""Reference suggestions reuse the real catalog and never invent missing matches."""

import pytest
from fastapi.testclient import TestClient
from api.api import app
from api import references, score, ciqual
from tests.helpers import (
    create_taxonomy,
    create_taxonomy_node,
    patch_ingredients_taxonomy,
    build_ingredient_obj,
)


@pytest.fixture(autouse=True)
def ciqual_catalog(monkeypatch):
    """Use distinct official CIQUAL names rather than the environmental labels."""
    foods = {
        "20001": {"code": "20001", "name_en": "Apple, raw", "name_fr": "Pomme, crue"},
        "90001": {"code": "90001", "name_en": "Independent food", "name_fr": "Aliment indépendant"},
    }
    monkeypatch.setattr(ciqual, "get_foods", lambda: foods)


def test_catalog_search_and_ciqual_links(agribalyse_index):
    """Search foods by name, exposing code links without nutrition composition claims."""
    client = TestClient(app)
    result = client.get("/v1/agribalyse/foods", params={"q": "APPLE"}).json()
    assert result["foods"][0]["code"] == "10001"
    assert result["foods"][0]["name"] == "Apple"
    result = client.get("/v1/nutrition/foods", params={"q": "apple"}).json()
    assert result["foods"][0]["ciqual_code"] == "20001"
    assert result["foods"][0]["name"] == "Apple, raw"
    assert (
        client.get("/v1/nutrition/foods", params={"q": "Independent"}).json()["foods"][0]["code"]
        == "90001"
    )
    assert (
        client.get("/v1/nutrition/foods", params={"q": "pomme", "lang": "fr"}).json()["foods"][0][
            "name"
        ]
        == "Pomme, crue"
    )
    assert client.get("/v1/agribalyse/foods", params={"q": ""}).json() == {"foods": []}
    assert client.get("/v1/agribalyse/foods", params={"q": "xxxzzzzz"}).json() == {"foods": []}
    assert client.get("/v1/agribalyse/foods", params={"limit": 0}).status_code == 422


@pytest.mark.asyncio
async def test_automatic_correspondence_and_unknown_ingredient(agribalyse_index):
    """Resolve a taxonomy mapping into named Agribalyse and CIQUAL correspondences."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await references.ingredient_references("en:apple")
        assert result.agribalyse is not None
        assert result.agribalyse.code == "10001"
        assert result.ciqual is not None
        assert result.ciqual.code == "20001"
        assert result.ciqual is not None
        assert result.ciqual.name == "Apple, raw"
        assert result.agribalyse is not None
        assert result.agribalyse.name == "Apple"
        assert result.source == "agribalyse_food_code"
        assert (await references.ingredient_references("en:unknown")).agribalyse is None


@pytest.mark.asyncio
async def test_manual_environmental_reference_affects_scoring(agribalyse_index):
    """The chef's explicit row choice overrides the taxonomy's environmental match."""
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple", properties={"agribalyse_food_code": {"en": "10001"}}
            )
        }
    )
    ingredient = build_ingredient_obj("i1", "apple", "en:apple")
    ingredient.agribalyse_code = "10002"
    with patch_ingredients_taxonomy(taxonomy):
        result = await score.match_ingredients_to_agribalyse([ingredient])
        assert result["i1"].agribalyse is not None
        assert result["i1"].agribalyse["code"] == "10002"
        assert result["i1"].code_source == "manual_agribalyse_code"
        ingredient.agribalyse_code = "does-not-exist"
        assert (await score.match_ingredients_to_agribalyse([ingredient]))["i1"].agribalyse is None


@pytest.mark.asyncio
async def test_retired_ciqual_link_uses_current_catalog(agribalyse_index, monkeypatch):
    """Missing old codes resolve to a real current food, never an environmental name."""
    monkeypatch.setattr(
        ciqual,
        "get_foods",
        lambda: {"90000": {"code": "90000", "name_en": "Apple, raw", "name_fr": "Pomme, crue"}},
    )
    taxonomy = create_taxonomy(
        {
            "en:apple": create_taxonomy_node(
                "en:apple",
                names={"en": "Apples"},
                properties={"agribalyse_food_code": {"en": "10001"}},
            )
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await references.ingredient_references("en:apple")
        assert result.ciqual is not None
        assert result.ciqual.code == "90000"
        assert result.ciqual is not None
        assert result.ciqual.name == "Apple, raw"
        monkeypatch.setattr(ciqual, "get_foods", lambda: {})
        assert (await references.ingredient_references("en:apple")).ciqual is None


@pytest.mark.asyncio
async def test_direct_ciqual_reference_does_not_require_agribalyse(monkeypatch):
    """Fresh cream must not become fresh cream cheese when Agribalyse has no cream row."""
    monkeypatch.setattr(
        ciqual,
        "get_foods",
        lambda: {
            "19402": {"code": "19402", "name_en": "Cream (average)", "name_fr": "Crème"},
            "19663": {"code": "19663", "name_en": "Fresh cream cheese", "name_fr": "Petit suisse"},
        },
    )
    taxonomy = create_taxonomy(
        {
            "en:fresh-cream": create_taxonomy_node(
                "en:fresh-cream",
                names={"en": "fresh cream"},
                properties={"ciqual_food_code": {"en": "19402"}},
            ),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await references.ingredient_references("en:fresh-cream")
    assert result.agribalyse is None
    assert result.ciqual.code == "19402"


@pytest.mark.asyncio
async def test_direct_ciqual_code_has_priority_over_an_environmental_proxy(agribalyse_index):
    """A valid explicit nutrition correspondence must survive an environmental proxy."""
    taxonomy = create_taxonomy(
        {
            "en:test": create_taxonomy_node(
                "en:test",
                properties={
                    "agribalyse_food_code": {"en": "10001"},
                    "ciqual_food_code": {"en": "90001"},
                },
            ),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        result = await references.ingredient_references("en:test")
    assert result.agribalyse.code == "10001"
    assert result.ciqual.code == "90001"


@pytest.mark.parametrize("code, missing", [("12118", ["sugars"]), ("28501", [])])
def test_ciqual_missing_data_matches_bundled_composition(code, missing):
    """Warn for unknown Emmental sugars without flagging complete raw lardons."""
    food = {"code": code, "name_en": "Food", "name_fr": "Aliment"}
    reference = references._ciqual_reference(food, "en")
    assert reference.missing_data == missing
    assert not reference.no_data


def test_missing_ciqual_composition_reports_all_required_fields():
    """An identity without composition cannot promise a usable nutrition reference."""
    food = {"code": "unknown", "name_en": "Food", "name_fr": "Aliment"}
    assert references._ciqual_reference(food, "en").missing_data == list(
        references.nutrition.REQUIRED
    )


def test_agribalyse_missing_environmental_data():
    """Only absent environmental scores need a warning; zero is a valid score."""
    assert references._reference({"code": "1", "score": None}).missing_data == [
        "environmental_data"
    ]
    assert references._reference({"code": "1", "score": 0}).missing_data == []
    assert references._reference({"code": "1", "score": None}).no_data
    assert not references._reference({"code": "1", "score": 0}).no_data
