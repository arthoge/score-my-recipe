"""Nutrition contracts: missing data, cooking, reference selection and upstream isolation."""

from unittest.mock import AsyncMock
from typing import cast

import pytest
from fastapi.testclient import TestClient

from api import nutrition, nutrition_data, nutriscore
from api.api import app


@pytest.fixture
def catalog(monkeypatch):
    """Small complete foods make mass normalization independently checkable."""
    values = {
        "energy_kj": "100",
        "saturated_fat": "0.1",
        "sugars": "1",
        "salt": "0.2",
        "fiber": "2",
        "proteins": "3",
        "fat": "1",
        "carbohydrates": "10",
    }

    def food(group="03", detail="030101"):
        """Complete composition for an ordinary solid ingredient."""
        return {
            "name": "Test food",
            "group": group,
            "subgroup": detail[:4],
            "detail_group": detail,
            "nutrients": values.copy(),
        }

    foods = {
        "9119": food(detail="030102"),
        "9125": food(),
        "20359": food("02", "020303"),
        "20360": food("02", "020301"),
        "4008": food("02", "020101"),
    }
    monkeypatch.setattr(nutrition_data, "get_foods", lambda: foods)
    monkeypatch.setattr(
        nutriscore,
        "calculate",
        AsyncMock(
            return_value=nutriscore.NutriScore(
                grade="B", score=1, components=nutriscore.ScoreComponents(negative=[], positive=[])
            )
        ),
    )
    return foods


def recipe(**changes):
    """One hundred grams of dry rice with an explicit generic nutrition reference."""
    row = {"id": "rice", "name": "Rice", "quantity_g": 100, "ciqual_code": "9119", **changes}
    return nutrition.NutritionRequest(
        ingredients=[nutrition.NutritionIngredient.model_validate(row)], portions=2
    )


@pytest.mark.parametrize(
    "raw,favorable,expected,limited",
    [
        ("0", False, 0, False),
        ("1,25", False, 1.25, False),
        ("< 0,5", False, 0.5, True),
        ("< 0,5", True, 0, True),
        ("-", False, None, False),
        ("traces", False, None, False),
        (None, False, None, False),
        ("NaN", False, None, False),
        ("-1", False, None, False),
    ],
)
def test_nutrient_values(raw, favorable, expected, limited):
    """Analytical zero is valid; unknown or unquantified values never silently become zero."""
    assert nutrition_data.nutrient_value(raw, favorable) == (expected, limited)


@pytest.mark.asyncio
async def test_cooking_and_portions(catalog):
    """Use prepared composition and mass once; portions do not change the per-100-g grade."""
    result = await nutrition.analyze(recipe(preparation="boiled"))
    assert result.status == "complete"
    assert result.prepared_weight_g == 298
    assert result.ingredients[0].prepared_reference == "9125"
    assert result.nutrients_total is not None
    assert result.nutrients_total["energy_kj"] == 298
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert result.nutrients_per_portion is not None
    assert result.nutrients_per_portion["energy_kj"] == 149
    assert result.ingredients[0].yield_source is not None
    assert result.ingredients[0].yield_source.version == "bognar-2002-v1"
    assert result.plant_percent == 0
    changed = recipe(preparation="boiled")
    changed.portions = 1
    assert (await nutrition.analyze(changed)).nutri_score == result.nutri_score


@pytest.mark.asyncio
async def test_measured_and_cooked(catalog):
    """A measured prepared mass scales prepared composition, not a second cooking yield."""
    result = await nutrition.analyze(recipe(preparation="boiled", prepared_weight_g=250))
    assert result.nutrients_total is not None
    assert result.nutrients_total["energy_kj"] == 250
    result = await nutrition.analyze(
        recipe(ciqual_code="9125", state="cooked", preparation="boiled")
    )
    assert result.prepared_weight_g == 100
    assert result.ingredients[0].prepared_reference == "9125"
    result = await nutrition.analyze(recipe(state="cooked"))
    assert result.status == "unsupported"
    assert result.diagnostics[0].code == "prepared_reference_required"


@pytest.mark.asyncio
async def test_missing_and_unsupported(catalog):
    """No grade is returned when no ingredient has complete usable composition."""
    result = await nutrition.analyze(recipe(ciqual_code="unknown"))
    assert result.nutri_score is None
    assert result.diagnostics[0].code == "nutrition_reference_missing"
    result = await nutrition.analyze(recipe(preparation="deep_fried", prepared_weight_g=90))
    assert result.status == "unsupported"
    catalog["9119"]["nutrients"]["fiber"] = "-"
    result = await nutrition.analyze(recipe())
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["fiber"] is None
    assert result.status == "incomplete"
    cast(AsyncMock, nutriscore.calculate).assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_recipe_plant_mass(catalog):
    """Legume proportions use rehydrated prepared mass, not a mean of ingredient grades."""
    request = recipe(preparation="boiled")
    request.ingredients.append(
        nutrition.NutritionIngredient(
            id="lentil", quantity_g=100, ciqual_code="20359", preparation="boiled"
        )
    )
    result = await nutrition.analyze(request)
    assert result.plant_percent == pytest.approx(273 / 571 * 100)
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == pytest.approx(100)
    catalog["20360"]["detail_group"] = "020404"
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert result.plant_percent == 0
    assert result.diagnostics[0].code == "plant_proportion_missing"


@pytest.mark.asyncio
async def test_off_reference_not_silently_replaced(catalog, monkeypatch):
    """An explicit OFF selection takes precedence; failure cannot switch to generic data."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(side_effect=OSError("offline")))
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "dependency_error"
    assert result.nutri_score is None
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value={"nutriments": {}}))
    result = await nutrition.analyze(recipe(barcode="123", preparation="deep_fried"))
    assert result.status == "unsupported"
    assert result.nutri_score is None


@pytest.mark.asyncio
async def test_upstream_grade_failure_preserves_nutrition(catalog, monkeypatch):
    """Composition remains usable if the independent OFF grade calculation fails."""
    monkeypatch.setattr(nutriscore, "calculate", AsyncMock(side_effect=ValueError("old algorithm")))
    result = await nutrition.analyze(recipe())
    assert result.status == "dependency_error"
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert result.nutri_score is None


def test_off_payload_and_result():
    """Use OFF's structured nutrition contract and reject errors or old-algorithm responses."""
    payload = nutriscore.calculation_payload({"energy_kj": 400, "salt": 0}, 50, "en:meals")
    assert "code" not in payload
    assert nutriscore.TEST_URL.endswith("/product/test")
    inputs = payload["product"]["nutrition"]["input_sets"][0]
    assert inputs["nutrients"]["energy-kj"] == {"value_string": "400", "unit": "kJ"}
    assert inputs["nutrients"]["fruits-vegetables-legumes"]["unit"] == "%"
    data = {
        "status": "success",
        "product": {
            "nutriscore": {
                "2023": {
                    "grade": "a",
                    "score": -1,
                    "data": {"components": {"positive": [], "negative": []}},
                }
            }
        },
    }
    assert nutriscore.parse_result(data).grade == "A"
    with pytest.raises(ValueError):
        nutriscore.parse_result({**data, "errors": ["ignored nutrients"]})
    with pytest.raises(ValueError):
        nutriscore.parse_result({"status": "success", "product": {"nutriscore": {"2021": {}}}})


def test_http_contract(catalog):
    """Invalid recipe inputs fail validation before any external calculation."""
    client = TestClient(app)
    payload = recipe(preparation="boiled").model_dump()
    assert client.post("/v1/nutrition/analyze", json=payload).json()["status"] == "complete"
    for portions in [0, -1, 1.5]:
        assert (
            client.post("/v1/nutrition/analyze", json={**payload, "portions": portions}).status_code
            == 422
        )
    assert (
        client.post("/v1/nutrition/analyze", json={**payload, "ingredients": []}).status_code == 422
    )


def test_bundled_catalog():
    """Official composition has all identities and retains zero, unknown and censored values."""
    foods = nutrition_data.get_foods()
    assert len(foods) == 3484
    assert foods["9119"]["nutrients"]["energy_kj"] == "1490"
    assert foods["9119"]["nutrients"]["sugars"] == "0"
    assert foods["9125"]["nutrients"]["sugars"] == "traces"


@pytest.mark.asyncio
async def test_off_complete_and_units(catalog, monkeypatch):
    """OFF per-100-g composition uses standardized units and the 2023 plant proportion."""
    raw = {
        "energy-kcal_100g": 100,
        "saturated-fat_100g": 0.1,
        "sugars_100g": 1,
        "sodium_100g": 0.1,
        "fiber_100g": 2,
        "proteins_100g": 3,
    }
    product = {
        "nutriments": raw,
        "nutriscore": {
            "2023": {
                "data": {
                    "components": {"positive": [{"id": "fruits_vegetables_legumes", "value": 40}]}
                }
            }
        },
    }
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value=product))
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == pytest.approx(418.4)
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["salt"] == 0.25
    assert result.ingredients[0].source == "Open Food Facts"
    assert result.plant_percent == 40
    raw.pop("fiber_100g")
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.ingredients[0].source == "CIQUAL-2025"
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["fiber"] == 2
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert any(issue.code == "off_ciqual_fallback" for issue in result.assumptions)


@pytest.mark.asyncio
async def test_red_meat_and_beverage_boundaries(catalog):
    """Quantified red meat reaches the 2023 cap; volume-less beverage requests are unsupported."""
    food = catalog["9119"]
    food.update(group="04", subgroup="0401", detail_group="040101", name="Beef, cooked")
    result = await nutrition.analyze(recipe())
    assert result.status == "complete"
    call = cast(AsyncMock, nutriscore.calculate).await_args
    assert call is not None
    assert call.args[3] == 100
    payload = nutriscore.calculation_payload({"energy_kj": 100}, 0, "en:meals", 25)
    assert payload["product"]["ingredients_text_en"] == "beef (25%), other ingredients (75%)"
    request = recipe()
    request.category = "en:beverages"
    assert (await nutrition.analyze(request)).status == "unsupported"


@pytest.mark.asyncio
async def test_exact_input_cache_and_reserved_endpoint(monkeypatch):
    """Only the non-persisting endpoint is called, and changed nutrition cannot reuse a grade."""
    response = {
        "status": "success",
        "product": {
            "nutriscore": {
                "2023": {
                    "grade": "b",
                    "score": 1,
                    "data": {"components": {"positive": [], "negative": []}},
                }
            }
        },
    }
    calls = []

    async def fetch(request):
        """Capture the contract without contacting any external service."""
        calls.append(request)
        return response

    monkeypatch.setattr(nutriscore, "fetch_json", fetch)
    nutriscore._calculate.cache_clear()
    await nutriscore.calculate({"energy_kj": 100}, 0)
    await nutriscore.calculate({"energy_kj": 100}, 0)
    await nutriscore.calculate({"energy_kj": 101}, 0)
    assert len(calls) == 2
    assert all(
        request.full_url == nutriscore.TEST_URL and request.method == "PATCH" for request in calls
    )
    nutriscore._calculate.cache_clear()


def test_published_off_reference():
    """Parse the published OFF cookies golden result without inventing an expected grade."""
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "nutriscore" / "cookies-2023.json"
    result = nutriscore.parse_result(json.loads(fixture.read_text()))
    assert result.version == "2023"
    assert result.grade == "E"
    assert result.score == 20
    assert result.components.negative[0].points == 10


@pytest.mark.asyncio
async def test_partial_grade_excludes_entire_missing_contributions(catalog):
    """Subset normalization excludes missing mass rather than silently counting it as zero."""
    catalog["20359"]["nutrients"]["fiber"] = "-"
    request = recipe()
    request.ingredients.extend(
        [
            nutrition.NutritionIngredient(
                id="incomplete", name="Lentils", quantity_g=200, ciqual_code="20359"
            ),
            nutrition.NutritionIngredient(id="missing", name="Custom food", quantity_g=100),
        ]
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert result.prepared_weight_g == 100
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["fiber"] == 2
    assert result.nutrients_per_portion is not None
    assert result.nutrients_per_portion["energy_kj"] == 50
    assert [row.ingredient_id for row in result.excluded_ingredients] == ["incomplete", "missing"]
    assert result.excluded_weight_percent == 75
    call = cast(AsyncMock, nutriscore.calculate).await_args
    assert call is not None
    assert call.args[0]["energy_kj"] == 100


@pytest.mark.asyncio
async def test_partial_grade_survives_product_lookup_failure(catalog, monkeypatch):
    """A failed explicit product lookup excludes only that row and does not change its source."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(side_effect=OSError("offline")))
    request = recipe()
    request.ingredients.append(
        nutrition.NutritionIngredient(
            id="product", name="Product", quantity_g=100, barcode="123", ciqual_code="9119"
        )
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.excluded_weight_percent == 50
    assert [row.ingredient_id for row in result.ingredients] == ["rice"]
    assert result.nutri_score is not None


@pytest.mark.asyncio
async def test_partial_grade_uses_prepared_weight_and_category_requirements(catalog):
    """Coverage uses prepared mass, and fat is required only for the fats/oils algorithm."""
    catalog["20360"]["nutrients"]["fat"] = "-"
    request = recipe(preparation="boiled")
    request.category = "en:fats"
    request.ingredients.append(
        nutrition.NutritionIngredient(
            id="lentil", name="Lentils", quantity_g=100, ciqual_code="20359", preparation="boiled"
        )
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.excluded_weight_percent == pytest.approx(273 / 571 * 100)
    assert result.excluded_ingredients[0].prepared_weight_g == 273
    request.category = "en:meals"
    assert (await nutrition.analyze(request)).status == "complete"


@pytest.mark.asyncio
async def test_all_excluded_retains_known_nutrition_without_grade(catalog):
    """Quantified nutrition stays visible when no row is sufficiently complete for a grade."""
    catalog["9119"]["nutrients"]["fiber"] = "-"
    result = await nutrition.analyze(recipe())
    assert result.status == "incomplete"
    assert result.excluded_weight_percent == 100
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["fiber"] is None
    assert result.nutri_score is None
    cast(AsyncMock, nutriscore.calculate).assert_not_awaited()


@pytest.mark.asyncio
async def test_incomplete_off_uses_complete_ciqual(catalog, monkeypatch):
    """Generic fallback replaces the whole composition and is explicitly reported by row."""
    monkeypatch.setattr(
        nutrition_data,
        "get_product",
        AsyncMock(return_value={"nutriments": {"energy-kj_100g": 999}}),
    )
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.excluded_ingredients == []
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert result.ingredients[0].reference == "9119"
    assert [(issue.code, issue.ingredient_id) for issue in result.assumptions] == [
        ("off_ciqual_fallback", "rice")
    ]


@pytest.mark.asyncio
async def test_incomplete_ciqual_cannot_claim_successful_fallback(catalog, monkeypatch):
    """Fallback must not turn missing generic values into zero or a blue success indicator."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value={"nutriments": {}}))
    catalog["9119"]["nutrients"]["fiber"] = "-"
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "incomplete"
    assert result.nutri_score is None
    assert result.excluded_ingredients[0].ingredient_id == "rice"
    assert not any(issue.code == "off_ciqual_fallback" for issue in result.assumptions)


@pytest.mark.asyncio
async def test_complete_off_still_takes_precedence(catalog, monkeypatch):
    """A complete product keeps its own composition even when generic Ciqual is available."""
    values = {
        ("energy-kj" if key == "energy_kj" else key.replace("_", "-")) + "_100g": 1
        for key in nutrition_data.COLUMNS
    }
    values["energy-kj_100g"] = 200
    values["fruits-vegetables-legumes_100g"] = 0
    monkeypatch.setattr(
        nutrition_data, "get_product", AsyncMock(return_value={"nutriments": values})
    )
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.ingredients[0].source == "Open Food Facts"
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 200
    assert not any(issue.code == "off_ciqual_fallback" for issue in result.assumptions)


@pytest.mark.asyncio
async def test_zero_quantity_excluded_without_lookup_or_mass(catalog, monkeypatch):
    """Zero quantity is excluded even if a stale manual prepared mass or OFF barcode remains."""
    lookup = AsyncMock(side_effect=AssertionError("Zero-quantity product must not be fetched"))
    monkeypatch.setattr(nutrition_data, "get_product", lookup)
    request = recipe()
    request.ingredients.append(
        nutrition.NutritionIngredient(
            id="zero", name="Unused", quantity_g=0, prepared_weight_g=500, barcode="123"
        )
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert result.prepared_weight_g == 100
    assert result.excluded_ingredients[0].ingredient_id == "zero"
    assert result.excluded_ingredients[0].prepared_weight_g == 0
    assert result.excluded_weight_percent == 0
    assert result.diagnostics[0].code == "zero_quantity"
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_zero_has_no_calculation(catalog):
    """All-zero requests have no nutrient table or grade and cannot divide by zero."""
    result = await nutrition.analyze(recipe(quantity_g=0))
    assert result.status == "incomplete"
    assert result.nutri_score is None
    assert result.nutrients_per_100g is None
    assert result.excluded_weight_percent == 0
    cast(AsyncMock, nutriscore.calculate).assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_quantity_draft_does_not_block_existing_recipe(catalog, monkeypatch):
    """An unfinished ingredient is excluded without dropping usable composition or fetching its product."""
    lookup = AsyncMock(side_effect=AssertionError("Draft product must not be fetched"))
    monkeypatch.setattr(nutrition_data, "get_product", lookup)
    request = recipe()
    request.ingredients.append(
        nutrition.NutritionIngredient(id="draft", name="New ingredient", barcode="123")
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert result.nutrients_per_100g is not None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert result.prepared_weight_g == 100
    assert result.excluded_ingredients[0].ingredient_id == "draft"
    assert result.diagnostics[0].code == "quantity_missing"
    lookup.assert_not_awaited()
    empty = await nutrition.analyze(
        nutrition.NutritionRequest(ingredients=[request.ingredients[-1]])
    )
    assert empty.nutri_score is None
    assert empty.nutrients_per_100g is None
