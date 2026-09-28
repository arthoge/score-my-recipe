"""Tests for ``recipes.recompute_quantity`` and the ``POST /v1/recompute-quantity`` endpoint.

The units taxonomy is mocked with a handful of nodes exercising the
``standard_unit`` and ``conversion_factor`` properties (mirroring the real OFF
units taxonomy where both are stored as language -> value dicts, e.g.
``{"en": "g"}`` and ``{"en": "1000"}``).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.api import app
from api import recipes
from api import exceptions

from tests.helpers import create_taxonomy, create_taxonomy_node, patch_language_check


client = TestClient(app)


@pytest.fixture
def mock_units_taxonomy():
    """Mock the OFF units taxonomy with mass, volume and property-less units.

    ``xx:g`` / ``xx:kg`` are mass units (standard_unit ``g``) with a conversion
    factor; ``en:cup`` is a volume unit (standard_unit ``ml``); ``en:piece``
    has no standard_unit (filtered out by ``get_units`` but still resolvable).
    """
    mock_nodes = [
        create_taxonomy_node(
            id="xx:g",
            names={"en": "gram", "xx": "g"},
            synonyms={"en": ["g", "grams"]},
            properties={"standard_unit": {"en": "g"}, "conversion_factor": {"en": "1"}},
        ),
        create_taxonomy_node(
            id="xx:kg",
            names={"en": "kilogram", "xx": "kg"},
            synonyms={"en": ["kg", "kilograms"]},
            properties={"standard_unit": {"en": "g"}, "conversion_factor": {"en": "1000"}},
        ),
        create_taxonomy_node(
            id="en:cup",
            names={"en": "cup", "xx": "cup"},
            synonyms={"en": ["cups"]},
            properties={"standard_unit": {"en": "ml"}, "conversion_factor": {"en": "240"}},
        ),
        create_taxonomy_node(
            id="en:piece",
            names={"en": "piece", "xx": "piece"},
            synonyms={"en": ["pieces"]},
        ),
    ]
    mocked_taxonomy = create_taxonomy(mock_nodes)

    # the endpoint validates the language via checks.check_language_code; stub it
    # so we don't hit the network and can control accepted codes ("en"/"fr")
    # reset the per-language caches so a previous run (with another taxonomy)
    # does not leak into this one
    recipes._get_units_entries.cache_clear()
    recipes._unit_name_to_id.cache_clear()
    try:
        with (
            patch("api.off.get_units_taxonomy", new_callable=AsyncMock) as mock_tax,
            patch_language_check(),
        ):
            mock_tax.return_value = mocked_taxonomy
            yield mock_tax
    finally:
        recipes._get_units_entries.cache_clear()
        recipes._unit_name_to_id.cache_clear()


# --- business logic --------------------------------------------------------


@pytest.mark.asyncio
async def test_same_unit_cross_multiplies(mock_units_taxonomy):
    """Case 1: unchanged unit -> quantity_g scales with the value ratio."""
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2, old_unit="xx:kg", new_value=3, new_unit="xx:kg", lang="en"
    )
    assert quantity_g == pytest.approx(3000)
    assert value == 3
    assert unit == "xx:kg"


@pytest.mark.asyncio
async def test_same_unit_name_cross_multiplies(mock_units_taxonomy):
    """Case 1 with unit *names* (e.g. parse output "kg"): the unit cancels out.

    No resolution is needed (and none performed) for a plain cross-multiplication;
    the input name is echoed back unchanged.
    """
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2, old_unit="kg", new_value=3, new_unit="kg", lang="en"
    )
    assert quantity_g == pytest.approx(3000)
    assert value == 3
    assert unit == "kg"


@pytest.mark.asyncio
async def test_same_item_unit_cross_multiplies(mock_units_taxonomy):
    """Case 1 with the item sentinel (e.g. 2 eggs -> 3 eggs)."""
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=120, old_value=2, old_unit="item", new_value=3, new_unit="item", lang="en"
    )
    assert quantity_g == pytest.approx(180)
    assert value == 3
    assert unit == "item"


@pytest.mark.asyncio
async def test_same_unit_zero_old_value_mass_unit_uses_factor(mock_units_taxonomy):
    """Case 1 with a zero old value and a mass unit falls back to the conversion factor.

    E.g. editing "0 kg" -> "2 kg" yields 2000 g (factor 1000).
    """
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=0, old_value=0, old_unit="xx:kg", new_value=2, new_unit="xx:kg", lang="en"
    )
    assert quantity_g == pytest.approx(2000)
    assert value == 2
    assert unit == "xx:kg"


@pytest.mark.asyncio
async def test_same_unit_zero_old_value_mass_unit_name_uses_factor(mock_units_taxonomy):
    """Case 1 zero-old-value fallback also resolves a unit *name* to its factor."""
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=0, old_value=0, old_unit="kg", new_value=2, new_unit="kg", lang="en"
    )
    assert quantity_g == pytest.approx(2000)
    assert value == 2
    assert unit == "kg"


@pytest.mark.asyncio
async def test_same_unit_zero_old_value_non_mass_unit_raises(mock_units_taxonomy):
    """Case 1 with a zero old value and a non-mass unit cannot be computed (-> 404)."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=0,
            old_value=0,
            old_unit="en:cup",
            new_value=2,
            new_unit="en:cup",
            lang="en",
        )


@pytest.mark.asyncio
async def test_same_item_unit_zero_old_value_raises(mock_units_taxonomy):
    """Case 1 with a zero old value and the item sentinel cannot be computed (-> 404)."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=0, old_value=0, old_unit="item", new_value=3, new_unit="item", lang="en"
        )


@pytest.mark.asyncio
async def test_change_to_mass_unit_uses_conversion_factor(mock_units_taxonomy):
    """Case 2: switch to a mass unit -> grams = new_value * conversion_factor."""
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2000, old_unit="xx:g", new_value=2, new_unit="xx:kg", lang="en"
    )
    assert quantity_g == pytest.approx(2000)
    assert value == 2
    assert unit == "xx:kg"


@pytest.mark.asyncio
async def test_change_to_mass_unit_name_uses_conversion_factor(mock_units_taxonomy):
    """Case 2 with a unit *name*: "kg" resolves to xx:kg (factor 1000).

    Mirrors the real discrepancy: parse returns quantity_unit "kg" (a name), and
    recompute must accept it.
    """
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2000, old_unit="g", new_value=2, new_unit="kg", lang="en"
    )
    assert quantity_g == pytest.approx(2000)
    assert value == 2
    assert unit == "kg"


@pytest.mark.asyncio
async def test_change_to_mass_unit_resolves_full_name(mock_units_taxonomy):
    """The full english label "kilogram" also resolves to xx:kg."""
    quantity_g, _, _ = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2000, old_unit="g", new_value=2, new_unit="kilogram", lang="en"
    )
    assert quantity_g == pytest.approx(2000)


@pytest.mark.asyncio
async def test_change_to_mass_unit_resolves_xx_abbreviation_for_other_lang(mock_units_taxonomy):
    """The "xx" abbreviation "kg" resolves even for a non-english language.

    "kg" is the neutral (xx) name of xx:kg, not present in the en translation set.
    """
    quantity_g, _, _ = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2000, old_unit="g", new_value=2, new_unit="kg", lang="fr"
    )
    assert quantity_g == pytest.approx(2000)


@pytest.mark.asyncio
async def test_unit_name_is_case_and_accent_insensitive(mock_units_taxonomy):
    """Unit name lookup normalizes case, accents and spaces."""
    # "Kg" (uppercase) resolves to xx:kg
    quantity_g, _, _ = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2000, old_unit="g", new_value=2, new_unit="Kg", lang="en"
    )
    assert quantity_g == pytest.approx(2000)


@pytest.mark.asyncio
async def test_change_from_item_to_mass_unit(mock_units_taxonomy):
    """Case 2: the old unit being 'item' is irrelevant, new_value drives the grams."""
    # was 2 eggs (quantity_g derived), now 5 kg -> 5000 g
    quantity_g, _, _ = await recipes.recompute_quantity(
        quantity_g=120, old_value=2, old_unit="item", new_value=5, new_unit="xx:kg", lang="en"
    )
    assert quantity_g == pytest.approx(5000)


@pytest.mark.asyncio
async def test_change_from_mass_to_volume_not_supported(mock_units_taxonomy):
    """Case 3: mass -> volume is not supported yet (-> 404)."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=2000,
            old_value=2000,
            old_unit="xx:g",
            new_value=2,
            new_unit="en:cup",
            lang="en",
        )


@pytest.mark.asyncio
async def test_change_from_mass_to_volume_name_not_supported(mock_units_taxonomy):
    """Case 3 with a unit *name*: "cup" resolves to en:cup (volume) -> not supported."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=2000, old_value=2000, old_unit="xx:g", new_value=2, new_unit="cup", lang="en"
        )


@pytest.mark.asyncio
async def test_change_from_mass_to_item_not_supported(mock_units_taxonomy):
    """Case 3: switching to a countable unit is not supported yet (-> 404)."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=2000,
            old_value=2000,
            old_unit="xx:g",
            new_value=3,
            new_unit="item",
            lang="en",
        )


@pytest.mark.asyncio
async def test_change_from_item_to_volume_not_supported(mock_units_taxonomy):
    """Case 3: item -> volume is not supported yet (-> 404)."""
    with pytest.raises(exceptions.UnitConversionNotSupportedError):
        await recipes.recompute_quantity(
            quantity_g=120, old_value=2, old_unit="item", new_value=1, new_unit="en:cup", lang="en"
        )


@pytest.mark.asyncio
async def test_unknown_new_unit_id_raises(mock_units_taxonomy):
    """An unknown new unit id is rejected (-> 422)."""
    with pytest.raises(exceptions.UnknownUnitError):
        await recipes.recompute_quantity(
            quantity_g=2000,
            old_value=2000,
            old_unit="xx:g",
            new_value=2,
            new_unit="en:nonsense",
            lang="en",
        )


@pytest.mark.asyncio
async def test_unknown_new_unit_name_raises(mock_units_taxonomy):
    """An unresolvable unit *name* is rejected as unknown (-> 422)."""
    with pytest.raises(exceptions.UnknownUnitError):
        await recipes.recompute_quantity(
            quantity_g=2000, old_value=2000, old_unit="g", new_value=2, new_unit="dozen", lang="en"
        )


@pytest.mark.asyncio
async def test_old_unit_name_not_resolved_in_cross_multiply(mock_units_taxonomy):
    """An unresolvable but consistent old unit still cross-multiplies (no regression).

    The unit cancels out in Case 1, so old_unit is never resolved/validated.
    """
    quantity_g, value, unit = await recipes.recompute_quantity(
        quantity_g=2000, old_value=2, old_unit="dozen", new_value=3, new_unit="dozen", lang="en"
    )
    assert quantity_g == pytest.approx(3000)
    assert value == 3
    assert unit == "dozen"


# --- HTTP endpoint ---------------------------------------------------------


def test_api_same_unit(mock_units_taxonomy):
    """POST /v1/recompute-quantity case 1 returns 200 with the scaled grams."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2,
            "old_unit": "xx:kg",
            "new_value": 3,
            "new_unit": "xx:kg",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quantityG"] == pytest.approx(3000)
    assert body["value"] == 3
    assert body["unit"] == "xx:kg"


def test_api_accepts_unit_name(mock_units_taxonomy):
    """The endpoint accepts a unit *name* and resolves it (echoes the name back)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "g",
            "new_value": 2,
            "new_unit": "kg",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quantityG"] == pytest.approx(2000)
    # the input name is echoed back unchanged
    assert body["unit"] == "kg"


def test_api_change_to_mass_unit(mock_units_taxonomy):
    """POST /v1/recompute-quantity case 2 returns 200 with new_value * factor."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "xx:g",
            "new_value": 2,
            "new_unit": "xx:kg",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantityG"] == pytest.approx(2000)


def test_api_change_to_volume_returns_404(mock_units_taxonomy):
    """Case 3 returns HTTP 404."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "xx:g",
            "new_value": 2,
            "new_unit": "en:cup",
        },
    )
    assert response.status_code == 404


def test_api_same_unit_zero_old_value_mass_unit(mock_units_taxonomy):
    """Case 1 with a zero old value and a mass unit falls back to the factor (200)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 0,
            "old_value": 0,
            "old_unit": "xx:kg",
            "new_value": 2,
            "new_unit": "xx:kg",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantityG"] == pytest.approx(2000)


def test_api_same_unit_zero_old_value_non_mass_returns_404(mock_units_taxonomy):
    """Case 1 with a zero old value and a volume unit returns HTTP 404."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 0,
            "old_value": 0,
            "old_unit": "en:cup",
            "new_value": 2,
            "new_unit": "en:cup",
        },
    )
    assert response.status_code == 404


def test_api_unknown_unit_returns_422(mock_units_taxonomy):
    """An unknown unit id returns HTTP 422."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "xx:g",
            "new_value": 2,
            "new_unit": "en:nonsense",
        },
    )
    assert response.status_code == 422


def test_api_unknown_unit_name_returns_422(mock_units_taxonomy):
    """An unresolvable unit *name* returns HTTP 422."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "g",
            "new_value": 2,
            "new_unit": "dozen",
        },
    )
    assert response.status_code == 422


def test_api_invalid_language_returns_422(mock_units_taxonomy):
    """An unsupported language code returns HTTP 422 (and does not hit the cache)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "zz",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "g",
            "new_value": 2,
            "new_unit": "kg",
        },
    )
    assert response.status_code == 422


def test_api_accepts_five_letter_language(mock_units_taxonomy):
    """A 5-letter language code (e.g. "en-US") is normalized and accepted."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en-US",
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "g",
            "new_value": 2,
            "new_unit": "kg",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantityG"] == pytest.approx(2000)


def test_api_missing_language_returns_422(mock_units_taxonomy):
    """A missing required lang field is rejected by validation (HTTP 422)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "quantity_g": 2000,
            "old_value": 2000,
            "old_unit": "g",
            "new_value": 2,
            "new_unit": "kg",
        },
    )
    assert response.status_code == 422


def test_api_negative_value_returns_422(mock_units_taxonomy):
    """A negative value is rejected by validation (HTTP 422)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2,
            "old_unit": "xx:g",
            "new_value": -5,
            "new_unit": "xx:g",
        },
    )
    assert response.status_code == 422


def test_api_accepts_camel_case_payload(mock_units_taxonomy):
    """The endpoint accepts the frontend camelCase payload."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantityG": 2000,
            "oldValue": 2,
            "oldUnit": "xx:kg",
            "newValue": 3,
            "newUnit": "xx:kg",
        },
    )
    assert response.status_code == 200
    assert response.json()["quantityG"] == pytest.approx(3000)


def test_api_response_uses_camel_case(mock_units_taxonomy):
    """The response field names are camelCase (quantityG, not quantity_g)."""
    response = client.post(
        "/v1/recompute-quantity",
        json={
            "lang": "en",
            "quantity_g": 2000,
            "old_value": 2,
            "old_unit": "xx:kg",
            "new_value": 3,
            "new_unit": "xx:kg",
        },
    )
    body = response.json()
    assert "quantityG" in body
    assert "quantity_g" not in body
