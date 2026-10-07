"""Cooking-aware recipe composition and independent Nutri-Score availability."""

import asyncio
import math
from typing import Literal

from pydantic import BaseModel, Field

from api import nutrition_data, nutriscore, preparation

REQUIRED = ("energy_kj", "saturated_fat", "sugars", "salt", "fiber", "proteins")
# Reviewed counterparts for the existing dry-food boiling profiles, without added salt.
PREPARED_FOODS = {
    ("9119", "boiled"): "9125",
    ("9821", "boiled"): "9822",
    ("20359", "boiled"): "20360",
}


class NutritionIngredient(preparation.PreparedWeightRequest):
    """Edible ingredient quantity, selected nutrition reference and optional measured mass."""

    id: str
    name: str = ""
    prepared_weight_g: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class NutritionRequest(BaseModel):
    """One served recipe component; category defaults to a solid dish, not a beverage."""

    ingredients: list[NutritionIngredient] = Field(min_length=1, max_length=100)
    portions: int = Field(default=1, ge=1, le=10000)
    category: Literal["en:meals", "en:beverages", "en:cheeses", "en:fats"] = "en:meals"


class Diagnostic(BaseModel):
    """Stable machine-readable problem or assumption, localized by the frontend."""

    ingredient_id: str | None = None
    ingredient_name: str | None = None
    code: str
    fields: list[str] = Field(default_factory=list)


class IngredientTrace(BaseModel):
    """Source, prepared counterpart and actual masses used for nutrient aggregation."""

    ingredient_id: str
    source: str
    reference: str
    prepared_reference: str
    prepared_weight_g: float
    yield_factor: float | None = None
    yield_source: preparation.YieldSource | None = None
    nutrients_per_100g: dict[str, float | None]
    plant_percent: float | None
    red_meat_percent: float | None = 0


class NutritionResponse(BaseModel):
    """Nutrition remains available if the independent grade dependency fails."""

    status: Literal["complete", "incomplete", "unsupported", "dependency_error"]
    nutri_score: nutriscore.NutriScore | None = None
    prepared_weight_g: float | None = None
    nutrients_total: dict[str, float | None] | None = None
    nutrients_per_100g: dict[str, float | None] | None = None
    nutrients_per_portion: dict[str, float | None] | None = None
    plant_percent: float | None = None
    ingredients: list[IngredientTrace] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    assumptions: list[Diagnostic] = Field(default_factory=list)
    data_version: str = "CIQUAL-2025"


def ciqual_plant_percent(food: dict) -> float | None:
    """Use official food groups, excluding tubers/nuts and unknown composite proportions.

    Concentrated/dried fruit and vegetable forms need the official reconstitution
    calculation and are deliberately not treated as equivalent fresh weight.
    """
    detail = food["detail_group"]
    if detail in ("020101", "020401", "020301", "020302"):
        return 100
    if food["subgroup"] in ("0201", "0203", "0204"):
        return None
    if food["group"] in ("00", "01", "08", "11") or food["subgroup"] in (
        "0602",
        "0704",
        "0709",
        "1001",
        "1002",
        "1003",
        "1009",
        "1010",
    ):
        return None
    return 0


def _ciqual_values(food: dict) -> tuple[dict, list[str]]:
    """Convert composition without confusing a missing value with an analytical zero."""
    values, bounded = {}, []
    for key, raw in food["nutrients"].items():
        values[key], limited = nutrition_data.nutrient_value(raw, key in ("fiber", "proteins"))
        if limited:
            bounded.append(key)
    return values, bounded


def _product_values(product: dict, prepared: bool) -> tuple[dict, float | None]:
    """Read standardized gram/kJ-per-100-g OFF values; never use per-serving numbers."""
    raw = product.get("nutriments", {})
    suffix = "_prepared_100g" if prepared else "_100g"
    keys = {"energy_kj": "energy-kj", "saturated_fat": "saturated-fat"}
    values = {
        key: nutrition_data.nutrient_value(raw.get(keys.get(key, key) + suffix))[0]
        for key in nutrition_data.COLUMNS
    }
    if values["energy_kj"] is None:
        kcal = nutrition_data.nutrient_value(raw.get("energy-kcal" + suffix))[0]
        if kcal is not None:
            values["energy_kj"] = kcal * 4.184
    if values["salt"] is None:
        sodium = nutrition_data.nutrient_value(raw.get("sodium" + suffix))[0]
        if sodium is not None:
            values["salt"] = sodium * 2.5
    # Accept explicit declared proportions, not a guessed zero for composite products.
    plant = nutrition_data.nutrient_value(raw.get("fruits-vegetables-legumes" + suffix))[0]
    if plant is not None and plant > 100:
        plant = None
    if plant is None and not prepared:
        # Reuse the upstream 2023 ingredient analysis, never the older nuts/oils percentage.
        data = product.get("nutriscore", {}).get("2023", {}).get("data", {})
        raw_percent = data.get("fruits_vegetables_legumes")
        if raw_percent is None:
            raw_percent = next(
                (
                    component.get("value")
                    for component in data.get("components", {}).get("positive", [])
                    if component.get("id") == "fruits_vegetables_legumes"
                ),
                None,
            )
        plant = nutrition_data.nutrient_value(raw_percent)[0]
        if plant is not None and plant > 100:
            plant = None
    return values, plant


async def analyze(request: NutritionRequest) -> NutritionResponse:
    """Aggregate complete prepared composition; never grade a subset of a recipe."""
    response = NutritionResponse(status="incomplete")
    if request.category == "en:beverages":
        # Gram quantities cannot establish per-100-ml composition or sweetener eligibility.
        response.status = "unsupported"
        response.diagnostics.append(Diagnostic(code="beverage_inputs_required"))
        return response
    foods = nutrition_data.get_foods()
    semaphore = asyncio.Semaphore(4)

    async def lookup(barcode: str) -> dict | None:
        """Limit parallel upstream requests for large recipes."""
        async with semaphore:
            return await nutrition_data.get_product(barcode)

    barcodes = {row.barcode for row in request.ingredients if row.barcode}
    products = dict(
        zip(
            barcodes,
            await asyncio.gather(
                *(lookup(barcode) for barcode in barcodes), return_exceptions=True
            ),
        )
    )
    unsupported, dependency_error = False, False
    for row in request.ingredients:

        def diagnostic(code: str, fields: list[str] | None = None) -> Diagnostic:
            """Attach an actionable issue to its recipe row."""
            return Diagnostic(
                ingredient_id=row.id, ingredient_name=row.name, code=code, fields=fields or []
            )

        estimate = preparation.estimate_prepared_weight(row)
        mass = row.prepared_weight_g or estimate.prepared_weight_g or row.quantity_g
        cooking = row.state == "raw" and row.preparation != "none"
        bounded = []
        red_meat = 0
        if row.barcode:
            product = products[row.barcode]
            if isinstance(product, BaseException):
                if not isinstance(product, Exception):
                    raise product
                dependency_error = True
                response.diagnostics.append(diagnostic("product_unavailable"))
                continue
            if not isinstance(product, dict) or not product:
                response.diagnostics.append(diagnostic("product_missing"))
                continue
            # Raw product nutrient values cannot describe nutrients lost/absorbed during cooking.
            values, plant = _product_values(product, cooking)
            if cooking and (estimate.status != "estimated" or values["energy_kj"] is None):
                unsupported = True
                response.diagnostics.append(diagnostic("unsupported_preparation"))
                continue
            source, reference, prepared_reference = "Open Food Facts", row.barcode, row.barcode
            upstream = product.get("nutriscore", {}).get("2023", {}).get("data", {})
            # An upstream meat-product flag is not an exact recipe ingredient percentage.
            if upstream.get("is_red_meat_product") or any(
                "meat" in tag or "sausage" in tag for tag in product.get("categories_tags", [])
            ):
                red_meat = None
                response.diagnostics.append(diagnostic("red_meat_proportion_missing"))
        else:
            if not row.ciqual_code:
                response.diagnostics.append(diagnostic("nutrition_reference_missing"))
                continue
            food = foods.get(row.ciqual_code)
            if not food:
                response.diagnostics.append(diagnostic("nutrition_reference_missing"))
                continue
            counterpart = row.ciqual_code
            if cooking:
                counterpart = PREPARED_FOODS.get((row.ciqual_code, row.preparation))
                if not counterpart or estimate.status != "estimated":
                    unsupported = True
                    response.diagnostics.append(diagnostic("unsupported_preparation"))
                    continue
                food = foods[counterpart]
            # A raw CIQUAL reference must not be used for an already cooked quantity.
            elif row.state in ("cooked", "drained") and (
                food["detail_group"] in ("020101", "020303", "030102")
                or ", cru" in food["name"].lower()
            ):
                unsupported = True
                response.diagnostics.append(diagnostic("prepared_reference_required"))
                continue
            values, bounded = _ciqual_values(food)
            if food["detail_group"] in ("040101", "040102", "040105", "040201", "040202", "040205"):
                red_meat = 100
            elif (
                food["group"] == "04"
                and food["subgroup"] not in ("0405", "0406", "0407", "0408", "0409", "0410")
                and food["detail_group"] not in ("040103", "040104", "040203", "040204")
            ):
                red_meat = None
                response.diagnostics.append(diagnostic("red_meat_proportion_missing"))
            plant = ciqual_plant_percent(food)
            source, reference, prepared_reference = "CIQUAL-2025", row.ciqual_code, counterpart
        if bounded:
            response.assumptions.append(diagnostic("conservative_nutrient_bounds", bounded))
        if cooking:
            response.assumptions.append(diagnostic("cooking_estimate"))
        missing = [key for key in REQUIRED if values[key] is None]
        if missing:
            response.diagnostics.append(diagnostic("nutrients_missing", missing))
        if plant is None:
            response.diagnostics.append(diagnostic("plant_proportion_missing"))
        response.ingredients.append(
            IngredientTrace(
                ingredient_id=row.id,
                source=source,
                reference=reference,
                prepared_reference=prepared_reference,
                prepared_weight_g=mass,
                yield_factor=estimate.yield_factor,
                yield_source=estimate.source,
                nutrients_per_100g=values,
                plant_percent=plant,
                red_meat_percent=red_meat,
            )
        )
    if len(response.ingredients) != len(request.ingredients):
        response.status = (
            "dependency_error"
            if dependency_error
            else ("unsupported" if unsupported else "incomplete")
        )
        return response
    traces = response.ingredients
    mass = sum(row.prepared_weight_g for row in traces)
    # A single missing contribution keeps the whole nutrient total unknown.
    totals: dict[str, float | None] = {}
    for key in nutrition_data.COLUMNS:
        contributions = []
        for trace in traces:
            value = trace.nutrients_per_100g[key]
            if value is None:
                totals[key] = None
                break
            contributions.append(value * trace.prepared_weight_g / 100)
        else:
            totals[key] = math.fsum(contributions)
    response.prepared_weight_g = mass
    response.nutrients_total = totals
    response.nutrients_per_100g = {
        key: None if value is None else value * 100 / mass for key, value in totals.items()
    }
    response.nutrients_per_portion = {
        key: None if value is None else value / request.portions for key, value in totals.items()
    }
    plant_mass, red_meat_mass = 0.0, 0.0
    for trace in traces:
        if trace.plant_percent is None or trace.red_meat_percent is None:
            return response
        plant_mass += trace.plant_percent * trace.prepared_weight_g / 100
        red_meat_mass += trace.red_meat_percent * trace.prepared_weight_g / 100
    response.plant_percent = plant_mass * 100 / mass
    if response.diagnostics:
        return response
    red_meat_percent = red_meat_mass * 100 / mass
    try:
        # Optional fat/carbohydrate composition may be absent; required score inputs may not.
        nutrients = {
            key: value for key, value in response.nutrients_per_100g.items() if value is not None
        }
        if request.category == "en:fats" and nutrients.get("fat") is None:
            response.diagnostics.append(Diagnostic(code="nutrients_missing", fields=["fat"]))
            return response
        response.nutri_score = await nutriscore.calculate(
            nutrients, response.plant_percent, request.category, red_meat_percent
        )
        response.status = "complete"
    except (OSError, ValueError, TimeoutError):
        response.status = "dependency_error"
        response.diagnostics.append(Diagnostic(code="calculation_unavailable"))
    return response
