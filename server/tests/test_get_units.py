"""Tests for the ``GET /v1/units`` endpoint and ``recipes.get_units``.

The units taxonomy is not part of the openfoodfacts SDK ``TaxonomyType`` enum,
so ``get_units`` fetches it through ``off.get_units_taxonomy``. The mock fixture
patches that fetcher with a small taxonomy exercising the ``standard_unit``
property (mirroring the real OFF units taxonomy where ``standard_unit`` is stored
as a language -> value dict, e.g. ``{"en": "ml"}``).
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
def mock_units_taxonomy():
    """Mock the OpenFoodFacts units taxonomy with 4 units.

    ``en:piece`` intentionally has no ``standard_unit`` property to exercise the
    optional/omitted case.
    """
    mock_nodes = [
        create_taxonomy_node(
            id="en:cup",
            names={"en": "cup", "fr": "tasse", "xx": "cup"},
            synonyms={"en": ["cups"], "fr": ["tasses"]},
            properties={"standard_unit": {"en": "ml"}},
        ),
        create_taxonomy_node(
            id="en:gram",
            names={"en": "gram", "fr": "gramme", "xx": "gram"},
            synonyms={"en": ["g", "grams"], "fr": ["g", "grammes"]},
            properties={"standard_unit": {"en": "g"}},
        ),
        create_taxonomy_node(
            id="en:kilojoule",
            names={"en": "kilojoule", "fr": "kilojoule", "xx": "kilojoule"},
            synonyms={"en": ["kilojoules"], "fr": ["kilojoules"]},
            properties={"standard_unit": {"en": "kJ"}},
        ),
        # no standard_unit property: must default to None (and be omitted by the API)
        create_taxonomy_node(
            id="en:piece",
            names={"en": "piece", "fr": "pièce", "xx": "piece"},
            synonyms={"en": ["pieces"], "fr": ["pièces"]},
        ),
    ]
    mocked_taxonomy = create_taxonomy(mock_nodes)

    # reset cache so a previous run (with another taxonomy) does not leak
    recipes._get_units_entries.cache_clear()
    try:
        with (
            patch("api.off.get_units_taxonomy", new_callable=AsyncMock) as mock,
            patch_language_check(),
        ):
            mock.return_value = mocked_taxonomy
            yield mock
    finally:
        recipes._get_units_entries.cache_clear()


def unit_list_to_dict(units: list[types.Unit]) -> dict[str, str]:
    """Convert a list of Unit objects to a {id: label} dict for comparison."""
    return {unit.id: unit.label for unit in units}


@pytest.mark.asyncio
async def test_get_units_filters_to_g_and_ml_standard_units(mock_units_taxonomy):
    """get_units only returns units whose standard_unit is g or ml.

    en:kilojoule (kJ) and en:piece (no standard_unit) must be excluded.
    """
    result = await recipes.get_units("en")
    assert isinstance(result, list)
    assert all(isinstance(unit, types.Unit) for unit in result)
    assert unit_list_to_dict(result) == {
        "en:cup": "cup",
        "en:gram": "gram",
    }
    # units with other (or no) standard_unit are filtered out
    assert all(unit.id not in ("en:kilojoule", "en:piece") for unit in result)


@pytest.mark.asyncio
async def test_get_units_returns_standard_unit(mock_units_taxonomy):
    """get_units populates the standard_unit property from the taxonomy."""
    result = await recipes.get_units("en")
    standard_unit_by_id = {unit.id: unit.standard_unit for unit in result}
    assert standard_unit_by_id["en:cup"] == "ml"
    assert standard_unit_by_id["en:gram"] == "g"


@pytest.mark.asyncio
async def test_get_units_uses_correct_language_labels(mock_units_taxonomy):
    """get_units returns labels in the requested language."""
    result_fr = await recipes.get_units("fr")
    assert unit_list_to_dict(result_fr) == {
        "en:cup": "tasse",
        "en:gram": "gramme",
    }


@pytest.mark.asyncio
async def test_get_units_handles_language_code_with_region(mock_units_taxonomy):
    """get_units strips the region from the language code (e.g. fr-FR -> fr)."""
    result_fr = await recipes.get_units("fr")
    result_frFR = await recipes.get_units("fr_FR")
    assert unit_list_to_dict(result_fr) == unit_list_to_dict(result_frFR)


@pytest.mark.asyncio
async def test_get_units_sorts_by_id(mock_units_taxonomy):
    """get_units returns units sorted by id for predictable ordering."""
    result = await recipes.get_units("en")
    ids = [unit.id for unit in result]
    assert ids == sorted(ids)


def test_get_units_api_returns_correct_data(mock_units_taxonomy):
    """The /v1/units endpoint returns the unit list with standard_unit."""
    response = client.get("/v1/units", params={"lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert "units" in data
    assert isinstance(data["units"], list)
    assert {unit["id"]: unit["label"] for unit in data["units"]} == {
        "en:cup": "cup",
        "en:gram": "gram",
    }


def test_get_units_api_returns_standard_unit(mock_units_taxonomy):
    """The /v1/units endpoint includes the standard_unit field when defined."""
    response = client.get("/v1/units", params={"lang": "en"})
    assert response.status_code == 200
    # use .get() as en:piece has no standard_unit (omitted by exclude_none)
    standard_unit_by_id = {
        unit["id"]: unit.get("standard_unit") for unit in response.json()["units"]
    }
    assert standard_unit_by_id["en:cup"] == "ml"
    assert standard_unit_by_id["en:gram"] == "g"


def test_get_units_api_excludes_non_g_ml_units(mock_units_taxonomy):
    """The /v1/units endpoint excludes units whose standard_unit is not g or ml."""
    response = client.get("/v1/units", params={"lang": "en"})
    assert response.status_code == 200
    ids = {unit["id"] for unit in response.json()["units"]}
    assert "en:kilojoule" not in ids
    assert "en:piece" not in ids


def test_get_units_api_cache_control_header(mock_units_taxonomy):
    """The /v1/units endpoint sets a 1-day Cache-Control header."""
    response = client.get("/v1/units", params={"lang": "en"})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400"


@pytest.mark.asyncio
async def test_get_units_excludes_synonyms_by_default(mock_units_taxonomy):
    """get_units does not populate synonyms when include_synonyms is False."""
    result = await recipes.get_units("en")
    assert all(unit.synonyms is None for unit in result)


@pytest.mark.asyncio
async def test_get_units_includes_synonyms_when_requested(mock_units_taxonomy):
    """get_units populates synonyms in the requested language when asked."""
    result = await recipes.get_units("en", include_synonyms=True)
    synonyms_by_id = {unit.id: unit.synonyms for unit in result}
    assert synonyms_by_id["en:gram"] == ["g", "grams"]
    assert synonyms_by_id["en:cup"] == ["cups"]


@pytest.mark.asyncio
async def test_get_units_synonyms_language_fallback(mock_units_taxonomy):
    """Synonyms fall back to english when not available in the requested language.

    en:cup has no spanish synonyms, so the english ones are returned.
    """
    result_es = await recipes.get_units("es", include_synonyms=True)
    cup = next(unit for unit in result_es if unit.id == "en:cup")
    assert cup.synonyms == ["cups"]


def test_get_units_api_synonyms_excluded_by_default(mock_units_taxonomy):
    """The /v1/units endpoint omits the synonyms field by default."""
    response = client.get("/v1/units", params={"lang": "en"})
    assert response.status_code == 200
    for unit in response.json()["units"]:
        assert "synonyms" not in unit


def test_get_units_api_returns_synonyms_when_requested(mock_units_taxonomy):
    """The /v1/units endpoint includes synonyms when include_synonyms=true."""
    response = client.get("/v1/units", params={"lang": "en", "include_synonyms": "true"})
    assert response.status_code == 200
    synonyms_by_id = {unit["id"]: unit["synonyms"] for unit in response.json()["units"]}
    assert synonyms_by_id["en:gram"] == ["g", "grams"]
    assert synonyms_by_id["en:cup"] == ["cups"]


def test_get_units_api_invalid_language_returns_422(mock_units_taxonomy):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    response = client.get("/v1/units", params={"lang": "zz"})
    assert response.status_code == 422
