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
    """An unavailable product without a generic reference cannot yield invented nutrition."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(side_effect=OSError("offline")))
    result = await nutrition.analyze(recipe(barcode="123", ciqual_code=None))
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
        "fat_100g": 1,
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
    request = recipe()
    request.category = "en:beverages"
    assert (await nutrition.analyze(request)).status == "unsupported"


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
            id="product", name="Product", quantity_g=100, barcode="123", ciqual_code=None
        )
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.excluded_weight_percent == 50
    assert [row.ingredient_id for row in result.ingredients] == ["rice"]
    assert result.nutri_score is not None


@pytest.mark.asyncio
async def test_partial_grade_uses_prepared_weight_and_category_requirements(catalog):
    """Coverage uses prepared mass; the OFF service requires total fat for meals too."""
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
    assert (await nutrition.analyze(request)).status == "partial"


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


@pytest.mark.asyncio
async def test_product_tags_survive_fallback_and_deduplicate(catalog, monkeypatch):
    """Keep reported tags from used products even when CIQUAL supplies their nutrition."""
    products = {
        "123": {
            "nutriments": {},
            "additives_tags": ["en:e322", "en:e322"],
            "allergens_tags": ["en:milk", "en:eggs"],
        },
        "456": {
            "nutriments": {},
            "additives_tags": ["en:e330", None],
            "allergens_tags": ["en:milk"],
        },
    }
    lookup = AsyncMock(side_effect=lambda code: products[code])
    monkeypatch.setattr(nutrition_data, "get_product", lookup)
    request = recipe(barcode="123")
    request.ingredients.extend(
        [
            nutrition.NutritionIngredient(
                id="second", name="Second", quantity_g=50, ciqual_code="9119", barcode="456"
            ),
            nutrition.NutritionIngredient(id="unused", name="Unused", quantity_g=0, barcode="789"),
        ]
    )
    result = await nutrition.analyze(request)
    assert result.additives == ["en:e322", "en:e330"]
    assert result.allergens == ["en:eggs", "en:milk"]
    assert all(row.source == "CIQUAL-2025" for row in result.ingredients)
    assert lookup.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "product", [None, {}, {"additives_tags": "en:e322", "allergens_tags": None}]
)
async def test_missing_product_tags_are_not_invented(catalog, monkeypatch, product):
    """Absent or malformed product composition yields no reported tags."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value=product))
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.additives == []
    assert result.allergens == []


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["28501", "28720", "28725"])
async def test_charcuterie_complete_composition_with_invariant_score(monkeypatch, code):
    """Real lardon references retain nutrients when the unknown meat share cannot change the score."""
    calculate = AsyncMock(
        return_value=nutriscore.NutriScore(
            grade="E", score=23, components=nutriscore.ScoreComponents(negative=[], positive=[])
        )
    )
    monkeypatch.setattr(nutriscore, "calculate", calculate)
    result = await nutrition.analyze(recipe(ciqual_code=code))
    assert result.status == "complete"
    assert result.excluded_ingredients == []
    assert result.ingredients[0].red_meat_percent is None
    assert not result.diagnostics
    assert [issue.code for issue in result.assumptions] == ["red_meat_score_invariant"]
    assert calculate.await_count == 2
    calls = calculate.await_args_list
    assert [call.args[3] for call in calls] == [0, 100]
    assert all(call.args[0][key] is not None for call in calls for key in nutrition.REQUIRED)
    if code == "28501":
        assert result.nutrients_per_100g["energy_kj"] == 1120
        assert result.nutrients_per_100g["proteins"] == 16.6
        assert result.nutrients_per_100g["salt"] == 2.72


@pytest.mark.asyncio
async def test_red_meat_bounds_are_weighted_on_the_whole_usable_recipe(catalog):
    """Bounds include known red meat and omit incomplete rows rather than testing each food alone."""
    catalog["20359"].update(group="04", subgroup="0403", detail_group="040308")
    catalog["4008"].update(group="04", subgroup="0401", detail_group="040101")
    request = recipe()
    request.ingredients.extend(
        [
            nutrition.NutritionIngredient(id="processed", quantity_g=200, ciqual_code="20359"),
            nutrition.NutritionIngredient(id="beef", quantity_g=100, ciqual_code="4008"),
            nutrition.NutritionIngredient(id="missing", quantity_g=100),
        ]
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.prepared_weight_g == 400
    assert [row.ingredient_id for row in result.excluded_ingredients] == ["missing"]
    calls = cast(AsyncMock, nutriscore.calculate).await_args_list
    assert [call.args[3] for call in calls] == [25, 75]
    assert result.plant_percent == 0


@pytest.mark.asyncio
async def test_red_meat_uncertainty_keeps_exclusion_when_numeric_scores_differ(catalog):
    """Matching letters alone are insufficient; keep the known subset when scores differ."""
    catalog["20359"].update(group="04", subgroup="0403", detail_group="040308")
    calculate = cast(AsyncMock, nutriscore.calculate)
    calculate.side_effect = [
        nutriscore.NutriScore(
            grade="B", score=1, components=nutriscore.ScoreComponents(negative=[], positive=[])
        ),
        nutriscore.NutriScore(
            grade="B", score=2, components=nutriscore.ScoreComponents(negative=[], positive=[])
        ),
        nutriscore.NutriScore(
            grade="B", score=1, components=nutriscore.ScoreComponents(negative=[], positive=[])
        ),
    ]
    request = recipe()
    request.ingredients.append(
        nutrition.NutritionIngredient(id="processed", quantity_g=100, ciqual_code="20359")
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.prepared_weight_g == 100
    assert result.excluded_ingredients[0].ingredient_id == "processed"
    assert result.diagnostics[0].code == "red_meat_proportion_missing"
    assert not any(issue.code == "red_meat_score_invariant" for issue in result.assumptions)
    assert calculate.await_count == 3


@pytest.mark.asyncio
async def test_score_invariant_ciqual_fallback_still_reported(catalog, monkeypatch):
    """An incomplete OFF meat product can use complete generic nutrition without false missing-data errors."""
    catalog["9119"].update(group="04", subgroup="0403", detail_group="040308")
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value={"nutriments": {}}))
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert not result.diagnostics
    assert result.ingredients[0].source == "CIQUAL-2025"
    assert {issue.code for issue in result.assumptions} == {
        "red_meat_score_invariant",
        "off_ciqual_fallback",
    }


@pytest.mark.asyncio
async def test_meat_bounds_do_not_override_missing_nutrients(catalog):
    """A missing required nutrient remains unknown even when meat sensitivity could be bounded."""
    catalog["9119"].update(group="04", subgroup="0403", detail_group="040308")
    catalog["9119"]["nutrients"]["fiber"] = "-"
    result = await nutrition.analyze(recipe())
    assert result.status == "incomplete"
    assert result.nutri_score is None
    assert result.nutrients_per_100g["fiber"] is None
    cast(AsyncMock, nutriscore.calculate).assert_not_awaited()


@pytest.mark.asyncio
async def test_meat_bounds_calculation_failure_preserves_nutrition(catalog, monkeypatch):
    """Unavailable grade comparisons must not discard known nutrient data or claim certainty."""
    catalog["9119"].update(group="04", subgroup="0403", detail_group="040308")
    monkeypatch.setattr(nutriscore, "calculate", AsyncMock(side_effect=OSError("offline")))
    result = await nutrition.analyze(recipe())
    assert result.status == "dependency_error"
    assert result.nutri_score is None
    assert result.nutrients_per_100g["energy_kj"] == 100
    assert {issue.code for issue in result.diagnostics} == {
        "red_meat_proportion_missing",
        "calculation_unavailable",
    }


@pytest.mark.asyncio
async def test_cooked_lardons_missing_sugars_remain_unknown(monkeypatch):
    """The distinct cooked reference really lacks sugars; raw composition cannot replace it."""
    calculate = AsyncMock()
    monkeypatch.setattr(nutriscore, "calculate", calculate)
    result = await nutrition.analyze(recipe(ciqual_code="28504", state="cooked"))
    assert result.status == "incomplete"
    assert result.nutrients_per_100g["sugars"] is None
    assert any(
        issue.code == "nutrients_missing" and issue.fields == ["sugars"]
        for issue in result.diagnostics
    )
    calculate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [OSError("OFF unavailable"), None, {}])
async def test_new_product_lookup_failure_preserves_generic_score(catalog, monkeypatch, failure):
    """Auto-selecting a replacement product must not discard an already usable CIQUAL reference."""
    lookup = (
        AsyncMock(side_effect=failure)
        if isinstance(failure, Exception)
        else AsyncMock(return_value=failure)
    )
    monkeypatch.setattr(nutrition_data, "get_product", lookup)
    before = await nutrition.analyze(recipe())
    after = await nutrition.analyze(recipe(barcode="123"))
    assert after.status == "complete"
    assert after.nutri_score == before.nutri_score
    assert after.nutrients_per_100g == before.nutrients_per_100g
    assert after.ingredients[0].source == "CIQUAL-2025"
    assert any(issue.code == "off_ciqual_fallback" for issue in after.assumptions)


@pytest.mark.asyncio
async def test_unavailable_product_without_generic_still_reports_failure(catalog, monkeypatch):
    """Fallback needs a real selected generic reference, not fabricated nutrition."""
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(side_effect=OSError("offline")))
    result = await nutrition.analyze(recipe(barcode="123", ciqual_code=None))
    assert result.status == "dependency_error"
    assert result.nutri_score is None


@pytest.mark.asyncio
async def test_product_missing_fat_falls_back_before_requesting_grade(catalog, monkeypatch):
    """OFF needs total fat even for meals; a barcode change cannot invalidate a complete generic food."""
    product = {
        "nutriments": {
            "energy-kj_100g": 200,
            "saturated-fat_100g": 1,
            "sugars_100g": 2,
            "salt_100g": 0.1,
            "fiber_100g": 3,
            "proteins_100g": 4,
            "fruits-vegetables-legumes_100g": 0,
        }
    }
    monkeypatch.setattr(nutrition_data, "get_product", AsyncMock(return_value=product))
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.ingredients[0].source == "CIQUAL-2025"
    assert cast(AsyncMock, nutriscore.calculate).call_args.args[0]["fat"] == 1


@pytest.mark.asyncio
async def test_missing_fat_or_references_excludes_only_unusable_rows(catalog):
    """An incomplete ingredient never nullifies the grade for remaining usable ingredients."""
    catalog["9125"]["nutrients"]["fat"] = "-"
    request = recipe()
    request.ingredients.extend(
        [
            nutrition.NutritionIngredient(
                id="missing-fat", name="Incomplete", quantity_g=50, ciqual_code="9125"
            ),
            nutrition.NutritionIngredient(id="missing-reference", name="Unknown", quantity_g=50),
        ]
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert {row.ingredient_id for row in result.excluded_ingredients} == {
        "missing-fat",
        "missing-reference",
    }
    assert result.excluded_weight_percent == 50
    assert result.nutrients_per_100g["fat"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {"nutriscore": None},
        {"nutriscore": {"2023": None}},
        {"nutriscore": {"2023": {"data": None}}},
        {"nutriscore": {"2023": {"data": {"components": None}}}},
        {"nutriscore": {"2023": {"data": {"components": {"positive": None}}}}},
        {"nutriscore": {"2023": {"data": {"components": {"positive": [None, "invalid"]}}}}},
        {"categories_tags": None},
        {"categories_tags": [None, 1]},
    ],
)
async def test_optional_product_metadata_cannot_abort_recipe(catalog, monkeypatch, metadata):
    """Incomplete OFF metadata must use CIQUAL or exclude one row, never fail the whole recipe."""
    monkeypatch.setattr(
        nutrition_data,
        "get_product",
        AsyncMock(
            return_value={
                "nutriments": {"energy-kj_100g": 500},
                **metadata,
            }
        ),
    )
    result = await nutrition.analyze(recipe(barcode="123"))
    assert result.status == "complete"
    assert result.nutri_score is not None
    assert result.ingredients[0].source == "CIQUAL-2025"
    request = recipe()
    request.ingredients.append(
        nutrition.NutritionIngredient(
            id="unusable", name="Missing product data", quantity_g=100, barcode="123"
        )
    )
    result = await nutrition.analyze(request)
    assert result.status == "partial"
    assert result.nutri_score is not None
    assert [row.ingredient_id for row in result.excluded_ingredients] == ["unusable"]
