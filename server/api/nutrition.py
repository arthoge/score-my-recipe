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

    quantity_g: float | None = Field(default=None, ge=0, allow_inf_nan=False)
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


class ExcludedIngredient(BaseModel):
    """Recipe ingredient excluded from the grade because its composition is incomplete."""

    ingredient_id: str
    ingredient_name: str
    prepared_weight_g: float


class NutritionResponse(BaseModel):
    """Nutrition remains available if the independent grade dependency fails."""

    status: Literal["complete", "partial", "incomplete", "unsupported", "dependency_error"]
    additives: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    nutri_score: nutriscore.NutriScore | None = None
    prepared_weight_g: float | None = None
    nutrients_total: dict[str, float | None] | None = None
    nutrients_per_100g: dict[str, float | None] | None = None
    nutrients_per_portion: dict[str, float | None] | None = None
    plant_percent: float | None = None
    ingredients: list[IngredientTrace] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    assumptions: list[Diagnostic] = Field(default_factory=list)
    excluded_ingredients: list[ExcludedIngredient] = Field(default_factory=list)
    excluded_weight_percent: float = 0
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
    if not isinstance(raw, dict):
        raw = {}
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


async def _red_meat_invariant_score(
    traces: list[IngredientTrace], category: str
) -> nutriscore.NutriScore | None:
    """Keep complete composition when every possible red-meat share gives the same score.

    The 2023 red-meat rule only caps protein points. Checking both mass-weighted
    endpoints avoids inventing a percentage for charcuterie or mixed meat foods.
    https://github.com/openfoodfacts/openfoodfacts-server/blob/main/lib/ProductOpener/Nutriscore.pm
    """
    mass = math.fsum(row.prepared_weight_g for row in traces)
    nutrients = {}
    for key in nutrition_data.COLUMNS:
        contributions = []
        for row in traces:
            value = row.nutrients_per_100g[key]
            if value is None:
                break
            contributions.append(value * row.prepared_weight_g)
        else:
            nutrients[key] = math.fsum(contributions) / mass
    plant_contributions = []
    for row in traces:
        assert row.plant_percent is not None
        plant_contributions.append(row.plant_percent * row.prepared_weight_g)
    plant = math.fsum(plant_contributions) / mass
    known_red_meat = (
        math.fsum((row.red_meat_percent or 0) * row.prepared_weight_g for row in traces) / mass
    )
    unknown_red_meat = (
        math.fsum(row.prepared_weight_g for row in traces if row.red_meat_percent is None)
        / mass
        * 100
    )
    lower, upper = await asyncio.gather(
        nutriscore.calculate(nutrients, plant, category, known_red_meat),
        nutriscore.calculate(nutrients, plant, category, known_red_meat + unknown_red_meat),
    )
    if (lower.version, lower.grade, lower.score) == (upper.version, upper.grade, upper.score):
        return upper
    return None


async def analyze(request: NutritionRequest) -> NutritionResponse:
    """Grade usable ingredients and explicitly report omitted rows and their weight share."""
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

    barcodes = {
        row.barcode
        for row in request.ingredients
        if row.barcode and row.quantity_g is not None and row.quantity_g > 0
    }
    products = dict(
        zip(
            barcodes,
            await asyncio.gather(
                *(lookup(barcode) for barcode in barcodes), return_exceptions=True
            ),
        )
    )
    # Product composition still matters when its nutrients fall back to CIQUAL.
    for field, target in (("additives_tags", "additives"), ("allergens_tags", "allergens")):
        tags = set()
        for product in products.values():
            if isinstance(product, dict) and isinstance(product.get(field), list):
                tags.update(tag for tag in product[field] if isinstance(tag, str) and tag.strip())
        setattr(response, target, sorted(tags))
    unsupported, dependency_error = False, False
    masses: dict[str, float] = {}
    fallback_ids: set[str] = set()
    for row in request.ingredients:

        def diagnostic(code: str, fields: list[str] | None = None) -> Diagnostic:
            """Attach an actionable issue to its recipe row."""
            return Diagnostic(
                ingredient_id=row.id, ingredient_name=row.name, code=code, fields=fields or []
            )

        if row.quantity_g is None:
            masses[row.id] = 0
            response.diagnostics.append(diagnostic("quantity_missing"))
            continue
        if row.quantity_g == 0:
            masses[row.id] = 0
            response.diagnostics.append(diagnostic("zero_quantity"))
            continue
        estimate = preparation.estimate_prepared_weight(row)
        mass = row.prepared_weight_g or estimate.prepared_weight_g or row.quantity_g
        masses[row.id] = mass
        cooking = row.state == "raw" and row.preparation != "none"
        bounded = []
        red_meat = 0
        required = (*REQUIRED, "fat") if request.category == "en:fats" else REQUIRED
        fallback = False
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
            source, reference, prepared_reference = "Open Food Facts", row.barcode, row.barcode
            upstream = product.get("nutriscore", {}).get("2023", {}).get("data", {})
            # An upstream meat-product flag is not an exact recipe ingredient percentage.
            if upstream.get("is_red_meat_product") or any(
                "meat" in tag or "sausage" in tag for tag in product.get("categories_tags", [])
            ):
                red_meat = None
            fallback = bool(row.ciqual_code in foods) and (
                any(values[key] is None for key in required) or plant is None or red_meat is None
            )
            if (
                cooking
                and (estimate.status != "estimated" or values["energy_kj"] is None)
                and not fallback
            ):
                unsupported = True
                response.diagnostics.append(diagnostic("unsupported_preparation"))
                continue
        if not row.barcode or fallback:
            red_meat = 0
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
            plant = ciqual_plant_percent(food)
            source, reference, prepared_reference = "CIQUAL-2025", row.ciqual_code, counterpart
        if bounded:
            response.assumptions.append(diagnostic("conservative_nutrient_bounds", bounded))
        if cooking:
            response.assumptions.append(diagnostic("cooking_estimate"))
        missing = [key for key in required if values[key] is None]
        if missing:
            response.diagnostics.append(diagnostic("nutrients_missing", missing))
        if plant is None:
            response.diagnostics.append(diagnostic("plant_proportion_missing"))
        if red_meat is None:
            response.diagnostics.append(diagnostic("red_meat_proportion_missing"))
        if fallback:
            fallback_ids.add(row.id)
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
    # An unknown meat proportion is not missing nutrient data. Only exclude it if
    # that uncertainty can change the grade or numeric score of the usable recipe.
    other_issues = {
        issue.ingredient_id
        for issue in response.diagnostics
        if issue.code != "red_meat_proportion_missing"
    }
    candidates = [row for row in response.ingredients if row.ingredient_id not in other_issues]
    uncertain_ids = {row.ingredient_id for row in candidates if row.red_meat_percent is None}
    invariant_score = None
    if uncertain_ids:
        try:
            invariant_score = await _red_meat_invariant_score(candidates, request.category)
        except (OSError, ValueError, TimeoutError):
            dependency_error = True
            response.diagnostics.append(Diagnostic(code="calculation_unavailable"))
        if invariant_score is not None:
            response.diagnostics = [
                issue
                for issue in response.diagnostics
                if not (
                    issue.code == "red_meat_proportion_missing"
                    and issue.ingredient_id in uncertain_ids
                )
            ]
            response.assumptions.extend(
                Diagnostic(
                    code="red_meat_score_invariant", ingredient_id=row.id, ingredient_name=row.name
                )
                for row in request.ingredients
                if row.id in uncertain_ids
            )
    excluded_ids = {issue.ingredient_id for issue in response.diagnostics if issue.ingredient_id}
    # Successful fallback describes the whole generic composition, including any
    # score-invariant uncertainty; incomplete fallbacks cannot claim success.
    response.assumptions.extend(
        Diagnostic(code="off_ciqual_fallback", ingredient_id=row.id, ingredient_name=row.name)
        for row in request.ingredients
        if row.id in fallback_ids and row.id not in excluded_ids
    )
    response.excluded_ingredients = [
        ExcludedIngredient(
            ingredient_id=row.id, ingredient_name=row.name, prepared_weight_g=masses[row.id]
        )
        for row in request.ingredients
        if row.id in excluded_ids
    ]
    total_mass = math.fsum(masses.values())
    response.excluded_weight_percent = (
        math.fsum(row.prepared_weight_g for row in response.excluded_ingredients) / total_mass * 100
        if total_mass > 0
        else 0
    )
    usable = [row for row in response.ingredients if row.ingredient_id not in excluded_ids]
    # If no complete ingredient remains, still expose quantified nutrition where available.
    # Those details have no grade, and missing contributions remain unknown.
    traces = usable or response.ingredients
    response.status = (
        "dependency_error" if dependency_error else ("unsupported" if unsupported else "incomplete")
    )
    if not traces:
        return response
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
    if not usable:
        return response
    plant_contributions, red_meat_contributions = [], []
    for trace in usable:
        assert trace.plant_percent is not None
        plant_contributions.append(trace.plant_percent * trace.prepared_weight_g / 100)
        red_meat_contributions.append((trace.red_meat_percent or 0) * trace.prepared_weight_g / 100)
    plant_mass = math.fsum(plant_contributions)
    red_meat_mass = math.fsum(red_meat_contributions)
    response.plant_percent = plant_mass * 100 / mass
    red_meat_percent = red_meat_mass * 100 / mass
    try:
        # Optional fat/carbohydrate composition may be absent; required score inputs may not.
        nutrients = {
            key: value for key, value in response.nutrients_per_100g.items() if value is not None
        }
        response.nutri_score = invariant_score or await nutriscore.calculate(
            nutrients, response.plant_percent, request.category, red_meat_percent
        )
        response.status = "partial" if response.excluded_ingredients else "complete"
    except (OSError, ValueError, TimeoutError):
        response.status = "dependency_error"
        response.diagnostics.append(Diagnostic(code="calculation_unavailable"))
    return response
