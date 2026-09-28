from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.api import app
from api import recipes
from api import types

from tests.helpers import (
    create_taxonomy,
    create_taxonomy_node,
    patch_language_check,
)


client = TestClient(app)


@pytest.fixture
def mock_countries_taxonomy():
    """Mock the OpenFoodFacts countries taxonomy with 4 countries"""
    mock_nodes = [
        create_taxonomy_node(
            id="en:france",
            names={"en": "France", "fr": "France", "xx": "France"},
            synonyms={"en": ["French Republic"], "fr": ["République française"]},
        ),
        create_taxonomy_node(
            id="en:italy",
            names={"en": "Italy", "it": "Italia", "fr": "Italie", "xx": "Italy"},
            synonyms={"en": ["Italian Republic"], "fr": ["République italienne"]},
        ),
        create_taxonomy_node(
            id="en:spain",
            names={"en": "Spain", "es": "España", "fr": "Espagne", "xx": "Spain"},
            synonyms={"en": ["Kingdom of Spain"], "fr": ["Royaume d'Espagne"]},
        ),
        create_taxonomy_node(
            id="en:germany",
            names={
                "en": "Germany",
                "de": "Deutschland",
                "fr": "Allemagne",
                "xx": "Germany",
            },
            synonyms={
                "en": ["Federal Republic of Germany"],
                "fr": ["République fédérale d'Allemagne"],
            },
        ),
    ]
    mocked_taxonomy = create_taxonomy(mock_nodes)

    with (
        patch("api.off.get_origins_taxonomy", new_callable=AsyncMock) as mock,
        patch_language_check(),
    ):
        mock.return_value = mocked_taxonomy
        yield mock


def origin_list_to_dict(origins: list[types.Origin]) -> dict[str, str]:
    """Convert a list of Origin objects to a dictionary for easier comparison"""
    return {origin.id: origin.label for origin in origins}


@pytest.mark.asyncio
async def test_get_origins_returns_correct_country_ids(mock_countries_taxonomy):
    """Test that get_origins returns correct taxonomy IDs"""
    result = await recipes.get_origins("en")
    assert isinstance(result, list)
    assert all(isinstance(origin, types.Origin) for origin in result)
    assert origin_list_to_dict(result) == {
        "en:france": "France",
        "en:italy": "Italy",
        "en:spain": "Spain",
        "en:germany": "Germany",
    }


@pytest.mark.asyncio
async def test_get_origins_uses_correct_language_labels(mock_countries_taxonomy):
    """Test that get_origins returns labels in requested language"""
    result_fr = await recipes.get_origins("fr")
    assert origin_list_to_dict(result_fr) == {
        "en:france": "France",
        "en:italy": "Italie",
        "en:spain": "Espagne",
        "en:germany": "Allemagne",
    }


@pytest.mark.asyncio
async def test_get_origins_handles_language_code_with_region(mock_countries_taxonomy):
    """Test that get_origins strips region from language code (e.g., fr-FR -> fr)"""
    result_fr = await recipes.get_origins("fr")
    result_frFR = await recipes.get_origins("fr_FR")
    assert origin_list_to_dict(result_fr) == origin_list_to_dict(result_frFR)


def test_get_origins_api_returns_correct_data(mock_countries_taxonomy):
    """Test that /v1/origins returns correct data"""
    response = client.get("/v1/origins", params={"lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert "origins" in data
    assert isinstance(data["origins"], list)
    assert {origin["id"]: origin["label"] for origin in data["origins"]} == {
        "en:france": "France",
        "en:italy": "Italy",
        "en:spain": "Spain",
        "en:germany": "Germany",
    }


def test_get_origins_api_cache_control_header(mock_countries_taxonomy):
    """Test that /v1/origins returns Cache-Control header for 1 day"""
    response = client.get("/v1/origins", params={"lang": "en"})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400"


@pytest.mark.asyncio
async def test_get_origins_excludes_synonyms_by_default(mock_countries_taxonomy):
    """Test that get_origins does not populate synonyms when include_synonyms is False"""
    result = await recipes.get_origins("en")
    assert all(origin.synonyms is None for origin in result)


@pytest.mark.asyncio
async def test_get_origins_includes_synonyms_when_requested(mock_countries_taxonomy):
    """Test that get_origins populates synonyms in the requested language"""
    result = await recipes.get_origins("en", include_synonyms=True)
    synonyms_by_id = {origin.id: origin.synonyms for origin in result}
    assert synonyms_by_id["en:france"] == ["French Republic"]
    assert synonyms_by_id["en:italy"] == ["Italian Republic"]


@pytest.mark.asyncio
async def test_get_origins_synonyms_language_fallback(mock_countries_taxonomy):
    """Test that synonyms fall back to english when not available in requested language"""
    # Italy has no spanish synonyms, should fall back to english
    result_es = await recipes.get_origins("es", include_synonyms=True)
    italy = next(origin for origin in result_es if origin.id == "en:italy")
    assert italy.synonyms == ["Italian Republic"]


def test_get_origins_api_synonyms_excluded_by_default(mock_countries_taxonomy):
    """Test that /v1/origins omits the synonyms field by default"""
    response = client.get("/v1/origins", params={"lang": "en"})
    assert response.status_code == 200
    for origin in response.json()["origins"]:
        assert "synonyms" not in origin


def test_get_origins_api_returns_synonyms_when_requested(mock_countries_taxonomy):
    """Test that /v1/origins includes synonyms when include_synonyms=true"""
    response = client.get("/v1/origins", params={"lang": "en", "include_synonyms": "true"})
    assert response.status_code == 200
    synonyms_by_id = {origin["id"]: origin["synonyms"] for origin in response.json()["origins"]}
    assert synonyms_by_id["en:france"] == ["French Republic"]
    assert synonyms_by_id["en:germany"] == ["Federal Republic of Germany"]


def test_get_origins_api_invalid_language_returns_422(mock_countries_taxonomy):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    response = client.get("/v1/origins", params={"lang": "zz"})
    assert response.status_code == 422
