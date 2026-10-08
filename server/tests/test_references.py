"""Reference suggestions reuse the real catalog and never invent missing matches."""

import pytest
import httpx
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
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        references.off, "get_ingredients_taxonomy", AsyncMock(return_value=create_taxonomy({}))
    )


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


@pytest.mark.asyncio
async def test_existing_codes_resolve_names_without_taxonomy(agribalyse_index, monkeypatch):
    """Imports and optimized rows hydrate labels and linked references independently."""
    from unittest.mock import AsyncMock
    from api import off

    taxonomy = AsyncMock(side_effect=OSError("offline"))
    monkeypatch.setattr(off, "get_ingredients_taxonomy", taxonomy)
    result = await references.resolve_ingredient_references(ciqual_code="20001", lang="fr")
    assert result.ciqual.name == "Pomme, crue"
    assert result.agribalyse.code == "10001"
    result = await references.resolve_ingredient_references(agribalyse_code="10001")
    assert result.ciqual.code == "20001"
    assert result.agribalyse.name == "Apple"
    taxonomy.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_name_search_resolves_without_a_taxonomy_id(agribalyse_index):
    """A full catalog label needs no taxonomy synonym to resolve linked databases."""
    result = await references.resolve_ingredient_references(query="Pomme, crue", lang="fr")
    assert result.ciqual.code == "20001"
    assert result.agribalyse.code == "10001"
    assert (await references.resolve_ingredient_references(query="zzzxunknown")).ciqual is None
    assert (
        await references.resolve_ingredient_references(ciqual_code="unknown", query="Pomme, crue")
    ).ciqual is None


@pytest.mark.asyncio
async def test_reference_api_accepts_codes_without_taxonomy(agribalyse_index):
    """The editor requests missing references from a chosen food, without a taxonomy node."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.get(
            "/v1/ingredient-references", params={"ciqual_code": "20001", "lang": "fr"}
        )
    assert result.status_code == 200
    assert result.json()["ciqual"]["name"] == "Pomme, crue"
    assert result.json()["agribalyse"]["code"] == "10001"


@pytest.mark.asyncio
async def test_taxonomy_can_fill_one_missing_database_without_overwriting_the_other(
    agribalyse_index, monkeypatch
):
    """A selected CIQUAL food does not disable independent environmental correspondence."""
    from unittest.mock import AsyncMock

    mapped = references.IngredientReferencesResponse(
        ciqual=references.FoodReference(code="20001", name="Mapped food"),
        agribalyse=references.FoodReference(code="10001", name="Environmental proxy"),
        source="taxonomy-proxy",
    )
    monkeypatch.setattr(references, "ingredient_references", AsyncMock(return_value=mapped))
    result = await references.resolve_ingredient_references("en:food", ciqual_code="90001")
    assert result.ciqual.code == "90001"
    assert result.agribalyse.code == "10001"
    assert result.source == "taxonomy-proxy"


@pytest.mark.asyncio
async def test_ciqual_resolution_survives_unavailable_environmental_data(monkeypatch):
    """An environmental catalog failure cannot hide an explicit nutritional reference."""
    from unittest.mock import Mock

    monkeypatch.setattr(
        references.agribalyse, "get_reference_rows", Mock(side_effect=OSError("offline"))
    )
    result = await references.resolve_ingredient_references(ciqual_code="20001")
    assert result.ciqual.code == "20001"
    assert result.agribalyse is None


@pytest.mark.asyncio
@pytest.mark.parametrize("taxonomy_id", [None, "en:unknown"])
async def test_short_name_falls_back_to_ranked_catalog_search(
    agribalyse_index, monkeypatch, taxonomy_id
):
    """Typed ingredient names need not exactly equal an official database label."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        references, "ingredient_references", AsyncMock(side_effect=OSError("offline"))
    )
    resolved = await references.resolve_ingredient_references(taxonomy_id, query="Pomme", lang="fr")
    assert resolved.ciqual.code == "20001"
    assert resolved.agribalyse.code == "10001"


@pytest.mark.asyncio
async def test_environmental_name_search_without_ciqual_match(agribalyse_index, monkeypatch):
    """CIQUAL missing a food must not disable independent Agribalyse name lookup."""
    monkeypatch.setattr(ciqual, "get_foods", lambda: {})
    resolved = await references.resolve_ingredient_references(query="Apple")
    assert resolved.ciqual is None
    assert resolved.agribalyse.code == "10001"


@pytest.mark.asyncio
async def test_typed_taxonomy_synonym_keeps_its_explicit_correspondence(agribalyse_index):
    """Moving name matching to the API must preserve the editor's synonym resolution."""
    taxonomy = create_taxonomy(
        {
            "en:independent": create_taxonomy_node(
                "en:independent",
                names={"en": "Independent food"},
                synonyms={"en": ["Orchard special"]},
                properties={"ciqual_food_code": {"en": "90001"}},
            ),
        }
    )
    with patch_ingredients_taxonomy(taxonomy):
        resolved = await references.resolve_ingredient_references(query="Orchard special")
    assert resolved.ciqual.code == "90001"


@pytest.mark.asyncio
async def test_environmental_name_fallback_preserves_resolved_food_preparation(monkeypatch):
    """Catalog releases with changed codes can still agree on a dry versus cooked food."""
    monkeypatch.setattr(
        ciqual,
        "get_foods",
        lambda: {
            "new": {
                "code": "new",
                "name_fr": "Lentille, sèche (aliment moyen)",
                "name_en": "Lentil, dried (average)",
            },
        },
    )
    monkeypatch.setattr(
        references.agribalyse,
        "get_reference_rows",
        lambda: [
            {
                "code": "cooked",
                "ciqual_code": "old-cooked",
                "name_fr": "Lentille, cuite",
                "score": 1,
            },
            {"code": "dry", "ciqual_code": "old-dry", "name_fr": "Lentille, sèche", "score": 2},
        ],
    )
    resolved = await references.resolve_ingredient_references(query="lentilles", lang="fr")
    assert resolved.ciqual.code == "new"
    assert resolved.agribalyse.code == "dry"


@pytest.mark.asyncio
async def test_environmental_fallback_simplifies_catalog_metadata(monkeypatch):
    """Long optimized labels still find a food variant when catalog codes differ."""
    monkeypatch.setattr(
        ciqual,
        "get_foods",
        lambda: {
            "new": {
                "code": "new",
                "name_fr": "Crème ou spécialité à base de crème légère, sans précision sur la teneur en matière grasse (aliment moyen)",
                "name_en": "",
            },
        },
    )
    monkeypatch.setattr(
        references.agribalyse,
        "get_reference_rows",
        lambda: [
            {
                "code": "cream",
                "ciqual_code": "old",
                "name_fr": "Crème 12 à 25% MG, légère, épaisse, rayon frais",
                "score": 1,
            },
            {
                "code": "dessert",
                "ciqual_code": "dessert",
                "name_fr": "Crème dessert au chocolat",
                "score": 2,
            },
        ],
    )
    resolved = await references.resolve_ingredient_references(
        query=ciqual.get_foods()["new"]["name_fr"], ciqual_code="new", lang="fr"
    )
    assert resolved.agribalyse.code == "cream"
