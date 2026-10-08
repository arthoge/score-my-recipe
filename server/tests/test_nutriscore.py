"""Local algorithm-2023 parity, threshold boundaries and independence from services."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from api import nutriscore, nutrition, nutrition_data, improvements
from api.recipe_analysis import ExportIngredient, ExportRecipe

REFERENCE = json.loads((Path(__file__).parent / "fixtures/nutriscore/local-2023.json").read_text())
BASE = {
    "energy_kj": 100,
    "sugars": 0,
    "fat": 1,
    "saturated_fat": 0,
    "salt": 0,
    "fiber": 0,
    "proteins": 0,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", REFERENCE["cases"])
async def test_matches_pinned_off_algorithm(case):
    """Compare points, grades and all component details against executed upstream code."""
    actual = await nutriscore.calculate(**case["input"])
    assert actual.model_dump(exclude={"version"}) == case["expected"]
    assert actual.version == "2023"


@pytest.mark.asyncio
async def test_matches_published_off_cookie_result():
    """Use OFF's published product fixture as an additional independent grade check."""
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/nutriscore/cookies-2023.json").read_text()
    )
    expected = fixture["product"]["nutriscore"]["2023"]
    actual = await nutriscore.calculate(
        {**BASE, "energy_kj": 3460, "fat": 90, "saturated_fat": 15}, 0
    )
    assert actual.score == expected["score"]
    assert actual.grade == expected["grade"].upper()


@pytest.mark.asyncio
async def test_recipe_changes_recalculate_without_a_score_service(monkeypatch):
    """An OFF outage cannot stop CIQUAL-backed optimization and final recalculation."""
    fetch = AsyncMock(side_effect=OSError("OFF unavailable"))
    monkeypatch.setattr(nutrition_data, "fetch_json", fetch)
    recipe = ExportRecipe(
        name="Cream recipe",
        ingredients=[
            ExportIngredient(
                id="cream",
                name="Crème fraîche",
                quantity_g=100,
                ciqual_code="19410",
                agribalyse_code="19410",
            )
        ],
    )
    before = await nutrition.analyze(nutrition.NutritionRequest.model_validate(recipe.model_dump()))
    preview = await improvements.find_improvements(
        improvements.ImprovementRequest(recipe=recipe, lang="fr")
    )
    assert before.nutri_score is not None
    assert preview.suggestions
    optimized = await improvements.optimize_recipe(
        improvements.OptimizeRequest(
            recipe=recipe, lang="fr", selected_ids=[preview.suggestions[0].id]
        )
    )
    after = await nutrition.analyze(
        nutrition.NutritionRequest.model_validate(optimized.recipe.model_dump())
    )
    assert after.nutri_score is not None
    assert after.nutrients_per_100g != before.nutrients_per_100g
    assert after.nutri_score.score == preview.suggestions[0].nutri_score.after
    assert optimized.recipe.ingredients[0].quantity_g == 100
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_plant_percentage_is_applied_directly():
    """Recipe plants must not be overwritten by remote synthetic ingredient parsing."""
    without = await nutriscore.calculate(BASE, 0)
    with_plants = await nutriscore.calculate(BASE, 81)
    assert with_plants.score == without.score - 5


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"salt": -1}, {"fat": float("nan")}, {"fiber": float("inf")}])
async def test_rejects_invalid_nutrients(changes):
    """Unknown/invalid composition cannot silently become a favorable zero."""
    with pytest.raises(ValueError):
        await nutriscore.calculate({**BASE, **changes}, 0)


@pytest.mark.asyncio
async def test_rejects_missing_nutrients_and_unsupported_categories():
    """The composition pipeline must resolve or exclude incomplete rows before scoring."""
    with pytest.raises(ValueError):
        await nutriscore.calculate({"energy_kj": 100}, 0)
    with pytest.raises(ValueError):
        await nutriscore.calculate(BASE, 101)
    with pytest.raises(ValueError):
        await nutriscore.calculate(BASE, 0, "en:beverages")


@pytest.mark.asyncio
async def test_weighted_percentage_roundoff_does_not_hide_a_score():
    """All-plant recipes remain computable when weighted arithmetic barely exceeds 100%."""
    exact = await nutriscore.calculate(BASE, 100)
    rounded = await nutriscore.calculate(BASE, 100.00000000000001)
    assert rounded == exact


@pytest.mark.asyncio
async def test_red_meat_cap_and_protein_gate_are_independent():
    """Apply the red-meat cap only above 10%, before the negative-point protein gate."""
    nutrients = {**BASE, "proteins": 20}
    uncapped = await nutriscore.calculate(nutrients, 0, red_meat_percent=10)
    capped = await nutriscore.calculate(nutrients, 0, red_meat_percent=10.01)
    assert uncapped.components.positive[0].points == 7
    assert capped.components.positive[0].points == 2
    gated = await nutriscore.calculate({**nutrients, "salt": 4}, 0)
    assert all(part.id != "proteins" for part in gated.components.positive)
    cheese = await nutriscore.calculate({**nutrients, "salt": 4}, 0, "en:cheeses")
    assert cheese.components.positive[0].id == "proteins"
