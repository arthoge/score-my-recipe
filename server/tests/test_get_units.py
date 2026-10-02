"""Tests for the ``GET /v1/units`` endpoint and ``units.get_units``.

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
from api import units
from api import types
from api import exceptions

from tests.helpers import (
    create_taxonomy,
    create_taxonomy_node,
    patch_ingredients_taxonomy,
    patch_language_check,
)


client = TestClient(app)


@pytest.fixture
def mock_units_taxonomy():
    """Mock the OpenFoodFacts units taxonomy with 6 units.

    Two mass units (``en:gram``, ``en:kilogram``), two volume units
    (``en:cup``, ``en:litre``), one energy unit (``en:kilojoule``, filtered out)
    and ``en:piece`` which intentionally has no ``standard_unit`` property to
    exercise the optional/omitted case.
    """
    mock_nodes = [
        create_taxonomy_node(
            id="en:cup",
            names={"en": "cup", "fr": "tasse", "xx": "cup"},
            synonyms={"en": ["cups"], "fr": ["tasses"]},
            properties={"standard_unit": {"en": "ml"}},
        ),
        create_taxonomy_node(
            id="en:litre",
            names={"en": "litre", "fr": "litre", "xx": "l"},
            synonyms={"en": ["litres"], "fr": ["litres"]},
            properties={"standard_unit": {"en": "ml"}},
        ),
        create_taxonomy_node(
            id="en:gram",
            names={"en": "gram", "fr": "gramme", "xx": "g"},
            synonyms={"en": ["g", "grams"], "fr": ["g", "grammes"]},
            properties={"standard_unit": {"en": "g"}},
        ),
        create_taxonomy_node(
            id="en:kilogram",
            names={"en": "kilogram", "fr": "kilogramme", "xx": "kg"},
            synonyms={"en": ["kg", "kilograms"], "fr": ["kg", "kilogrammes"]},
            properties={"standard_unit": {"en": "g"}},
        ),
        create_taxonomy_node(
            id="en:kilojoule",
            names={"en": "kilojoule", "fr": "kilojoule", "xx": "kj"},
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
    units._get_units_entries.cache_clear()
    try:
        with (
            patch("api.off.get_units_taxonomy", new_callable=AsyncMock) as mock,
            patch_language_check(),
        ):
            mock.return_value = mocked_taxonomy
            yield mock
    finally:
        units._get_units_entries.cache_clear()


def unit_list_to_dict(units: list[types.Unit]) -> dict[str, str]:
    """Convert a list of Unit objects to a {id: label} dict for comparison."""
    return {unit.id: unit.label for unit in units}


@pytest.mark.asyncio
async def test_get_units_filters_to_g_and_ml_standard_units(mock_units_taxonomy):
    """get_units only returns units whose standard_unit is g or ml.

    en:kilojoule (kJ) and en:piece (no standard_unit) must be excluded.
    """
    result = await units.get_units("en")
    assert isinstance(result, list)
    assert all(isinstance(unit, types.Unit) for unit in result)
    assert unit_list_to_dict(result) == {
        "en:cup": "cup",
        "en:gram": "gram",
        "en:kilogram": "kilogram",
        "en:litre": "litre",
    }
    # units with other (or no) standard_unit are filtered out
    assert all(unit.id not in ("en:kilojoule", "en:piece") for unit in result)


@pytest.mark.asyncio
async def test_get_units_returns_standard_unit(mock_units_taxonomy):
    """get_units populates the standard_unit property from the taxonomy."""
    result = await units.get_units("en")
    standard_unit_by_id = {unit.id: unit.standard_unit for unit in result}
    assert standard_unit_by_id["en:cup"] == "ml"
    assert standard_unit_by_id["en:gram"] == "g"
    assert standard_unit_by_id["en:kilogram"] == "g"
    assert standard_unit_by_id["en:litre"] == "ml"


@pytest.mark.asyncio
async def test_get_units_uses_correct_language_labels(mock_units_taxonomy):
    """get_units returns labels in the requested language."""
    result_fr = await units.get_units("fr")
    assert unit_list_to_dict(result_fr) == {
        "en:cup": "tasse",
        "en:gram": "gramme",
        "en:kilogram": "kilogramme",
        "en:litre": "litre",
    }


@pytest.mark.asyncio
async def test_get_units_handles_language_code_with_region(mock_units_taxonomy):
    """get_units strips the region from the language code (e.g. fr-FR -> fr)."""
    result_fr = await units.get_units("fr")
    result_frFR = await units.get_units("fr_FR")
    assert unit_list_to_dict(result_fr) == unit_list_to_dict(result_frFR)


@pytest.mark.asyncio
async def test_get_units_sorts_by_id(mock_units_taxonomy):
    """get_units returns units sorted by id for predictable ordering."""
    result = await units.get_units("en")
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
        "en:kilogram": "kilogram",
        "en:litre": "litre",
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
    assert standard_unit_by_id["en:kilogram"] == "g"
    assert standard_unit_by_id["en:litre"] == "ml"


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
    result = await units.get_units("en")
    assert all(unit.synonyms is None for unit in result)


@pytest.mark.asyncio
async def test_get_units_includes_synonyms_when_requested(mock_units_taxonomy):
    """get_units populates synonyms in the requested language when asked."""
    result = await units.get_units("en", include_synonyms=True)
    synonyms_by_id = {unit.id: unit.synonyms for unit in result}
    assert synonyms_by_id["en:gram"] == ["g", "grams"]
    assert synonyms_by_id["en:cup"] == ["cups"]


@pytest.mark.asyncio
async def test_get_units_synonyms_language_fallback(mock_units_taxonomy):
    """Synonyms fall back to english when not available in the requested language.

    en:cup has no spanish synonyms, so the english ones are returned.
    """
    result_es = await units.get_units("es", include_synonyms=True)
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


# ---------------------------------------------------------------------------
# Compatibility filtering (compatible_with_unit + ingredient_id)
# ---------------------------------------------------------------------------


def _mock_ingredients_taxonomy():
    """Mock ingredients taxonomy with average_weight_per_unit variations.

    * ``en:egg`` has a positive average_weight_per_unit (50 g).
    * ``en:water`` has no average_weight_per_unit property.
    * ``en:zero-weight`` has a zero average_weight_per_unit (must be treated
      as absent per the "positive number" rule).
    """
    nodes = [
        create_taxonomy_node(
            id="en:egg",
            names={"en": "egg", "xx": "egg"},
            synonyms={"en": ["eggs"]},
            properties={"average_weight_per_unit": {"en": "50"}},
        ),
        create_taxonomy_node(
            id="en:water",
            names={"en": "water", "xx": "water"},
            synonyms={"en": []},
        ),
        create_taxonomy_node(
            id="en:zero-weight",
            names={"en": "zero weight", "xx": "zero weight"},
            synonyms={"en": []},
            properties={"average_weight_per_unit": {"en": "0"}},
        ),
    ]
    return create_taxonomy(nodes)


@pytest.fixture
def mock_units_and_ingredients(mock_units_taxonomy):
    """Mock both the units and ingredients taxonomies for compatibility tests.

    Builds on :func:`mock_units_taxonomy` (6 units: cup/litre are ml, gram/kilogram
    are g, kilojoule/kJ filtered out, piece/none filtered out) and patches the
    ingredients taxonomy with the egg/water/zero-weight nodes.
    """
    ingredients_taxonomy = _mock_ingredients_taxonomy()
    with patch_ingredients_taxonomy(ingredients_taxonomy):
        yield ingredients_taxonomy


# --- business logic: filtering by source unit ------------------------------


@pytest.mark.asyncio
async def test_get_units_compatible_with_g_returns_only_g_units(mock_units_and_ingredients):
    """Source 'en:gram' (g): only g units are compatible (item not included)."""
    result = await units.get_units("en", compatible_with_unit="en:gram")
    ids = [unit.id for unit in result]
    assert ids == ["en:gram", "en:kilogram"]
    # item must not appear (no ingredient provided, source is not 'item')
    assert types.ITEM_UNIT not in ids


@pytest.mark.asyncio
async def test_get_units_compatible_with_ml_returns_g_and_ml_units(
    mock_units_and_ingredients,
):
    """Source 'en:cup' (ml): g units (always) + ml units (same standard_unit)."""
    result = await units.get_units("en", compatible_with_unit="en:cup")
    ids = [unit.id for unit in result]
    assert ids == ["en:cup", "en:gram", "en:kilogram", "en:litre"]


@pytest.mark.asyncio
async def test_get_units_compatible_with_item_returns_g_units_and_item(
    mock_units_and_ingredients,
):
    """Source 'item': all g units + the synthetic item unit."""
    result = await units.get_units("en", compatible_with_unit=types.ITEM_UNIT)
    ids = [unit.id for unit in result]
    assert ids == ["en:gram", "en:kilogram", "item"]


@pytest.mark.asyncio
async def test_get_units_compatible_with_source_as_name(mock_units_and_ingredients):
    """Source given as a localized name ('g') is resolved and filters correctly."""
    result = await units.get_units("en", compatible_with_unit="g")
    ids = [unit.id for unit in result]
    assert ids == ["en:gram", "en:kilogram"]


# --- business logic: item target with ingredient ---------------------------


@pytest.mark.asyncio
async def test_get_units_item_compatible_with_ingredient_avg_weight(
    mock_units_and_ingredients,
):
    """Source 'g' + ingredient with positive average_weight_per_unit: item is added."""
    result = await units.get_units(
        "en", compatible_with_unit="en:gram", ingredient_id="en:egg"
    )
    ids = [unit.id for unit in result]
    assert "item" in ids
    assert "en:gram" in ids


@pytest.mark.asyncio
async def test_get_units_item_not_compatible_without_ingredient(
    mock_units_and_ingredients,
):
    """Source 'ml' without ingredient: no item in results."""
    result = await units.get_units("en", compatible_with_unit="en:cup")
    assert types.ITEM_UNIT not in [unit.id for unit in result]


@pytest.mark.asyncio
async def test_get_units_item_not_compatible_ingredient_without_avg_weight(
    mock_units_and_ingredients,
):
    """Ingredient without average_weight_per_unit: item is not compatible."""
    result = await units.get_units(
        "en", compatible_with_unit="en:gram", ingredient_id="en:water"
    )
    assert types.ITEM_UNIT not in [unit.id for unit in result]


@pytest.mark.asyncio
async def test_get_units_item_not_compatible_ingredient_zero_avg_weight(
    mock_units_and_ingredients,
):
    """Ingredient with zero average_weight_per_unit: item is not compatible."""
    result = await units.get_units(
        "en", compatible_with_unit="en:gram", ingredient_id="en:zero-weight"
    )
    assert types.ITEM_UNIT not in [unit.id for unit in result]


@pytest.mark.asyncio
async def test_get_units_item_compatible_source_item_and_ingredient(
    mock_units_and_ingredients,
):
    """Source 'item' + ingredient: item is compatible (source rule takes over)."""
    result = await units.get_units(
        "en", compatible_with_unit=types.ITEM_UNIT, ingredient_id="en:water"
    )
    ids = [unit.id for unit in result]
    assert "item" in ids
    assert "en:gram" in ids


# --- business logic: synthetic item unit properties ------------------------


@pytest.mark.asyncio
async def test_get_units_item_unit_has_no_standard_unit(mock_units_and_ingredients):
    """The synthetic item unit has standard_unit=None (omitted from JSON)."""
    result = await units.get_units("en", compatible_with_unit=types.ITEM_UNIT)
    item_unit = next(unit for unit in result if unit.id == types.ITEM_UNIT)
    assert item_unit.standard_unit is None
    assert item_unit.label == types.ITEM_UNIT


@pytest.mark.asyncio
async def test_get_units_item_unit_synonyms_empty_when_requested(
    mock_units_and_ingredients,
):
    """When include_synonyms=true, the item unit gets an empty synonyms list."""
    result = await units.get_units(
        "en", include_synonyms=True, compatible_with_unit=types.ITEM_UNIT
    )
    item_unit = next(unit for unit in result if unit.id == types.ITEM_UNIT)
    assert item_unit.synonyms == []


@pytest.mark.asyncio
async def test_get_units_item_unit_no_synonyms_when_not_requested(
    mock_units_and_ingredients,
):
    """When include_synonyms=false, the item unit has synonyms=None."""
    result = await units.get_units("en", compatible_with_unit=types.ITEM_UNIT)
    item_unit = next(unit for unit in result if unit.id == types.ITEM_UNIT)
    assert item_unit.synonyms is None


@pytest.mark.asyncio
async def test_get_units_item_sorted_alphabetically(mock_units_and_ingredients):
    """The synthetic item unit is sorted alphabetically by id."""
    result = await units.get_units("en", compatible_with_unit=types.ITEM_UNIT)
    ids = [unit.id for unit in result]
    assert ids == sorted(ids)
    # 'item' sorts after 'en:...' ids ('e' < 'i')
    assert ids[-1] == "item"


# --- business logic: no filtering ------------------------------------------


@pytest.mark.asyncio
async def test_get_units_no_filtering_returns_all_g_ml_units(mock_units_taxonomy):
    """When compatible_with_unit is omitted, the full g/ml list is returned."""
    result = await units.get_units("en")
    ids = [unit.id for unit in result]
    # today's behavior: only g/ml taxonomy units, no item
    assert ids == ["en:cup", "en:gram", "en:kilogram", "en:litre"]
    assert types.ITEM_UNIT not in ids


# --- error handling ---------------------------------------------------------


@pytest.mark.asyncio
async def test_get_units_unknown_source_unit_raises(mock_units_and_ingredients):
    """An unresolvable source unit raises UnknownUnitError."""
    with pytest.raises(exceptions.UnknownUnitError):
        await units.get_units("en", compatible_with_unit="en:nonexistent")


@pytest.mark.asyncio
async def test_get_units_non_g_ml_source_unit_raises(mock_units_and_ingredients):
    """A source unit with a non g/ml standard_unit raises UnknownUnitError."""
    with pytest.raises(exceptions.UnknownUnitError):
        await units.get_units("en", compatible_with_unit="en:kilojoule")


@pytest.mark.asyncio
async def test_get_units_unknown_ingredient_raises(mock_units_and_ingredients):
    """An unknown ingredient id raises UnknownIngredientError."""
    with pytest.raises(exceptions.UnknownIngredientError):
        await units.get_units(
            "en", compatible_with_unit="en:gram", ingredient_id="en:nonexistent"
        )


# --- API endpoint -----------------------------------------------------------


def test_get_units_api_compatible_with_g(mock_units_and_ingredients):
    """The /v1/units endpoint filters by compatible_with_unit."""
    response = client.get(
        "/v1/units", params={"lang": "en", "compatible_with_unit": "en:gram"}
    )
    assert response.status_code == 200
    ids = [unit["id"] for unit in response.json()["units"]]
    assert ids == ["en:gram", "en:kilogram"]


def test_get_units_api_compatible_with_item(mock_units_and_ingredients):
    """The /v1/units endpoint includes the synthetic item unit."""
    response = client.get(
        "/v1/units", params={"lang": "en", "compatible_with_unit": "item"}
    )
    assert response.status_code == 200
    ids = [unit["id"] for unit in response.json()["units"]]
    assert ids == ["en:gram", "en:kilogram", "item"]


def test_get_units_api_compatible_with_ingredient(mock_units_and_ingredients):
    """The /v1/units endpoint adds item when ingredient has avg_weight_per_unit."""
    response = client.get(
        "/v1/units",
        params={
            "lang": "en",
            "compatible_with_unit": "en:gram",
            "ingredient_id": "en:egg",
        },
    )
    assert response.status_code == 200
    ids = [unit["id"] for unit in response.json()["units"]]
    assert "item" in ids


def test_get_units_api_unknown_source_returns_422(mock_units_and_ingredients):
    """An unresolvable source unit returns HTTP 422."""
    response = client.get(
        "/v1/units", params={"lang": "en", "compatible_with_unit": "en:nonexistent"}
    )
    assert response.status_code == 422


def test_get_units_api_unknown_ingredient_returns_422(mock_units_and_ingredients):
    """An unknown ingredient id returns HTTP 422."""
    response = client.get(
        "/v1/units",
        params={
            "lang": "en",
            "compatible_with_unit": "en:gram",
            "ingredient_id": "en:nonexistent",
        },
    )
    assert response.status_code == 422


def test_get_units_api_ingredient_without_source_returns_422(mock_units_and_ingredients):
    """Providing ingredient_id without compatible_with_unit returns HTTP 422."""
    response = client.get(
        "/v1/units", params={"lang": "en", "ingredient_id": "en:egg"}
    )
    assert response.status_code == 422
