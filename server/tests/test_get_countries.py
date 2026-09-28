"""Tests for the ``GET /v1/countries`` endpoint and ``recipes.get_countries``.

``get_countries`` filters the countries taxonomy to only keep countries that
also appear as an origin (via ``off.origins_by_country_code``), so the mock
fixture patches both the countries taxonomy and the origins mapping.
"""

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
    """Mock the countries taxonomy and the origins-by-country-code mapping.

    The taxonomy holds 5 countries but only 4 are referenced by
    ``origins_by_country_code``; ``en:taiwan`` is intentionally left out to
    exercise the filtering logic.
    """
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
        # not referenced as an origin: must be filtered out
        create_taxonomy_node(
            id="en:taiwan",
            names={"en": "Taiwan", "xx": "Taiwan"},
            synonyms={"en": ["Republic of China"]},
        ),
    ]
    mocked_taxonomy = create_taxonomy(mock_nodes)

    # only France, Italy, Spain and Germany are origins
    mocked_origins = {
        "FR": "en:france",
        "IT": "en:italy",
        "ES": "en:spain",
        "DE": "en:germany",
    }

    # reset cache
    recipes.get_countries_entries.cache_clear()
    try:
        with (
            patch("api.off.get_countries_taxonomy", new_callable=AsyncMock) as mock_tax,
            patch("api.off.origins_by_country_code", new_callable=AsyncMock) as mock_origins,
            patch_language_check(),
        ):
            mock_tax.return_value = mocked_taxonomy
            mock_origins.return_value = mocked_origins
            yield mock_tax
    finally:
        recipes.get_countries_entries.cache_clear()


def country_list_to_dict(countries: list[types.Country]) -> dict[str, str]:
    """Convert a list of Country objects to a {id: label} dict for comparison."""
    return {country.id: country.label for country in countries}


@pytest.mark.asyncio
async def test_get_countries_returns_only_origin_countries(mock_countries_taxonomy):
    """get_countries only returns countries that are also origins."""
    result = await recipes.get_countries("en")
    assert isinstance(result, list)
    assert all(isinstance(country, types.Country) for country in result)
    assert country_list_to_dict(result) == {
        "en:france": "France",
        "en:italy": "Italy",
        "en:spain": "Spain",
        "en:germany": "Germany",
    }


@pytest.mark.asyncio
async def test_get_countries_excludes_non_origin_countries(mock_countries_taxonomy):
    """Countries not referenced as an origin (e.g. Taiwan) are filtered out."""
    result = await recipes.get_countries("en")
    assert all(country.id != "en:taiwan" for country in result)


@pytest.mark.asyncio
async def test_get_countries_uses_correct_language_labels(mock_countries_taxonomy):
    """get_countries returns labels in the requested language."""
    result_fr = await recipes.get_countries("fr")
    assert country_list_to_dict(result_fr) == {
        "en:france": "France",
        "en:italy": "Italie",
        "en:spain": "Espagne",
        "en:germany": "Allemagne",
    }


@pytest.mark.asyncio
async def test_get_countries_handles_language_code_with_region(mock_countries_taxonomy):
    """get_countries strips the region from the language code (e.g. fr-FR -> fr)."""
    result_fr = await recipes.get_countries("fr")
    result_frFR = await recipes.get_countries("fr_FR")
    assert country_list_to_dict(result_fr) == country_list_to_dict(result_frFR)


@pytest.mark.asyncio
async def test_get_countries_sorts_by_id(mock_countries_taxonomy):
    """get_countries returns countries sorted by id for predictable ordering."""
    result = await recipes.get_countries("en")
    ids = [country.id for country in result]
    assert ids == sorted(ids)


def test_get_countries_api_returns_correct_data(mock_countries_taxonomy):
    """The /v1/countries endpoint returns the filtered country list."""
    response = client.get("/v1/countries", params={"lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert "countries" in data
    assert isinstance(data["countries"], list)
    assert {country["id"]: country["label"] for country in data["countries"]} == {
        "en:france": "France",
        "en:italy": "Italy",
        "en:spain": "Spain",
        "en:germany": "Germany",
    }
    # the non-origin country must not leak through the API
    assert all(country["id"] != "en:taiwan" for country in data["countries"])


def test_get_countries_api_cache_control_header(mock_countries_taxonomy):
    """The /v1/countries endpoint sets a 1-day Cache-Control header."""
    response = client.get("/v1/countries", params={"lang": "en"})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400"


@pytest.mark.asyncio
async def test_get_countries_excludes_synonyms_by_default(mock_countries_taxonomy):
    """get_countries does not populate synonyms when include_synonyms is False."""
    result = await recipes.get_countries("en")
    assert all(country.synonyms is None for country in result)


@pytest.mark.asyncio
async def test_get_countries_includes_synonyms_when_requested(mock_countries_taxonomy):
    """get_countries populates synonyms in the requested language when asked."""
    result = await recipes.get_countries("en", include_synonyms=True)
    synonyms_by_id = {country.id: country.synonyms for country in result}
    assert synonyms_by_id["en:france"] == ["French Republic"]
    assert synonyms_by_id["en:italy"] == ["Italian Republic"]


@pytest.mark.asyncio
async def test_get_countries_synonyms_language_fallback(mock_countries_taxonomy):
    """Synonyms fall back to english when not available in the requested language.

    Italy has no spanish synonyms, so the english ones are returned.
    """
    result_es = await recipes.get_countries("es", include_synonyms=True)
    italy = next(country for country in result_es if country.id == "en:italy")
    assert italy.synonyms == ["Italian Republic"]


def test_get_countries_api_synonyms_excluded_by_default(mock_countries_taxonomy):
    """The /v1/countries endpoint omits the synonyms field by default."""
    response = client.get("/v1/countries", params={"lang": "en"})
    assert response.status_code == 200
    for country in response.json()["countries"]:
        assert "synonyms" not in country


def test_get_countries_api_returns_synonyms_when_requested(mock_countries_taxonomy):
    """The /v1/countries endpoint includes synonyms when include_synonyms=true."""
    response = client.get("/v1/countries", params={"lang": "en", "include_synonyms": "true"})
    assert response.status_code == 200
    synonyms_by_id = {
        country["id"]: country["synonyms"] for country in response.json()["countries"]
    }
    assert synonyms_by_id["en:france"] == ["French Republic"]
    assert synonyms_by_id["en:germany"] == ["Federal Republic of Germany"]


def test_get_countries_api_invalid_language_returns_422(mock_countries_taxonomy):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    response = client.get("/v1/countries", params={"lang": "zz"})
    assert response.status_code == 422
