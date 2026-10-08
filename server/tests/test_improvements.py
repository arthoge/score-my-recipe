"""Recipe improvement contracts: valid references, coverage, trade-offs and combined swaps."""

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from api import improvements, nutrition, nutriscore, types
from api.api import app
from api.recipe_analysis import ExportRecipe


def recipe(**changes):
    """A recipe with two deliberately identical names and different row identifiers."""
    return ExportRecipe.model_validate(
        {
            "name": "Yogurt bowl",
            "portions": 2,
            "country": "FR",
            "ingredients": [
                {"id": "first", "name": "Yogurt", "quantity_g": 100, "ciqual_code": "19580"},
                {"id": "second", "name": "Yogurt", "quantity_g": 50, "ciqual_code": "19580"},
            ],
            **changes,
        }
    )


def result(item=None, green=50, nutri=10, missing=None, status="complete"):
    """Complete comparable grades without upstream network requests."""
    return (
        item,
        types.GreenScoreResponse(
            numeric_score=green, letter_grade="C", missing_ingredient_ids=missing or []
        ),
        nutrition.NutritionResponse(
            status=status,
            nutri_score=nutriscore.NutriScore(
                grade="c",
                score=nutri,
                components=nutriscore.ScoreComponents(positive=[], negative=[]),
            ),
        ),
    )


@pytest.fixture
def catalogs(monkeypatch):
    """Resolve one catalog alternative to bounded in-memory official reference data."""
    monkeypatch.setattr(
        improvements.ciqual,
        "get_foods",
        lambda: {
            "19594": {"code": "19594", "name_en": "Plain yogurt", "name_fr": "Yaourt nature"},
        },
    )
    monkeypatch.setattr(
        improvements.nutrition_data,
        "get_foods",
        lambda: {
            "19580": {"name": "Yaourt, sucré", "subgroup": "0502", "nutrients": {}},
            "19594": {"name": "Yaourt, nature", "subgroup": "0502", "nutrients": {}},
        },
    )
    monkeypatch.setattr(
        improvements.agribalyse,
        "get_reference_rows",
        lambda: [
            {
                "code": "valid-green",
                "ciqual_code": "19594",
                "name_fr": "Yaourt nature",
                "score": 0.1,
            },
        ],
    )


@pytest.mark.parametrize(
    "old,new,direction,expected",
    [
        (50, 60, "green", 20),
        (10, 5, "nutri", 50),
        (-5, -6, "nutri", 20),
        (0, -1, "nutri", None),
        (0, 10, "green", None),
    ],
)
def test_directional_percentages(old, new, direction, expected):
    """Numeric percentages preserve direction, including negative and zero baselines."""
    before = result(
        green=old if direction == "green" else 50, nutri=old if direction == "nutri" else 10
    )
    after = result(
        green=new if direction == "green" else 50, nutri=new if direction == "nutri" else 10
    )
    green, nutri, safe = improvements.score_changes(before, after)
    assert safe
    assert (green if direction == "green" else nutri).percent == expected
    assert improvements.improves(green, nutri)


def test_tradeoffs_are_visible_but_lost_coverage_is_rejected():
    """An improvement can disclose a regression but cannot drop ingredients from the score."""
    green, nutri, safe = improvements.score_changes(result(), result(green=60, nutri=11))
    assert safe
    assert green.percent == 20
    assert nutri.percent == -10
    assert not improvements.score_changes(result(), result(green=60, missing=["first"]))[2]
    partial = result(status="partial")
    partial[2].excluded_ingredients = [
        nutrition.ExcludedIngredient(
            ingredient_id="first", ingredient_name="Yogurt", prepared_weight_g=100
        )
    ]
    assert not improvements.score_changes(result(), partial)[2]
    green, nutri, safe = improvements.score_changes(result(missing=["first"]), result(green=60))
    assert green is None
    assert safe
    assert not improvements.improves(green, nutri)


def test_resolved_food_replacement_invalidates_product_metadata(catalogs):
    """The swap supplies valid codes, without inventing taxonomy or certification data."""
    row = recipe().ingredients[0]
    row.labels = [types.TaxonomyItem(id="en:organic", label="Organic", is_in_taxonomy=True)]
    row.origin = types.TaxonomyItem(id="en:france", label="France", is_in_taxonomy=True)
    suggestion = improvements.food_candidates(row, "en")[0]
    assert suggestion.after.id == "first"
    assert suggestion.after.quantity_g == 100
    assert suggestion.after.ciqual_code == "19594"
    assert suggestion.after.agribalyse_code == "valid-green"
    assert suggestion.after.codified_ingredient is None
    assert suggestion.after.labels == []
    assert suggestion.after.origin is None
    row.state = "cooked"
    assert improvements.food_candidates(row, "en") == []


@pytest.mark.asyncio
async def test_check_and_optimize_keep_duplicate_rows_separate(monkeypatch, catalogs):
    """Selecting the second yogurt row leaves the first untouched and verifies both scores."""

    async def calculate(item):
        changed = sum(row.ciqual_code == "19594" for row in item.ingredients)
        return result(item, green=50 + changed * 5, nutri=10 - changed * 2)

    calculator = AsyncMock(side_effect=calculate)
    monkeypatch.setattr(improvements, "calculate_report", calculator)
    request = improvements.ImprovementRequest(recipe=recipe())
    response = await improvements.find_improvements(request)
    assert [row.ingredient_id for row in response.suggestions] == ["first", "second"]
    assert response.suggestions[0].green_score.percent == 10
    optimized = await improvements.optimize_recipe(
        improvements.OptimizeRequest(
            recipe=request.recipe,
            selected_ids=[response.suggestions[1].id],
        )
    )
    assert optimized.recipe.ingredients[0].ciqual_code == "19580"
    assert optimized.recipe.ingredients[1].ciqual_code == "19594"
    assert optimized.recipe.portions == 2
    assert optimized.recipe.country == "FR"
    assert request.recipe.ingredients[1].ciqual_code == "19580"


@pytest.mark.asyncio
async def test_unsafe_combination_and_unknown_selections_are_rejected(monkeypatch, catalogs):
    """Individual gains do not authorize a combination whose recalculated nutrition regresses."""

    async def calculate(item):
        changed = sum(row.ciqual_code == "19594" for row in item.ingredients)
        return result(
            item,
            green=45 if changed == 2 else 50 + changed * 5,
            nutri=11 if changed == 2 else 10 - changed,
        )

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    with pytest.raises(ValueError, match="combined"):
        await improvements.optimize_recipe(
            improvements.OptimizeRequest(
                recipe=recipe(),
                selected_ids=["first:ciqual:19594", "second:ciqual:19594"],
            )
        )
    with pytest.raises(ValueError, match="no longer"):
        await improvements.optimize_recipe(
            improvements.OptimizeRequest(
                recipe=recipe(),
                selected_ids=["invented"],
            )
        )


@pytest.mark.asyncio
async def test_product_candidates_use_real_same_category_barcodes(monkeypatch):
    """OFF candidates preserve generic food identity but discard old product claims."""
    monkeypatch.setattr(
        improvements.nutrition_data,
        "get_product",
        AsyncMock(
            return_value={
                "categories_tags": ["en:dairies", "en:yogurts"],
            }
        ),
    )
    monkeypatch.setattr(
        improvements.off,
        "search_products",
        AsyncMock(
            return_value=[
                {"code": "222", "product_name": "Plain yogurt", "categories_tags": ["en:yogurts"]},
                {"code": "333", "product_name": "Unrelated", "categories_tags": ["en:desserts"]},
                {"code": "111", "product_name": "Original", "categories_tags": ["en:yogurts"]},
            ]
        ),
    )
    row = recipe().ingredients[0]
    row.barcode = "111"
    row.agribalyse_code = "generic-yogurt"
    candidate = (await improvements.product_candidates(row, "en"))[0]
    assert candidate.category == "open_food_facts"
    assert candidate.after.barcode == "222"
    assert candidate.after.ciqual_code is None
    assert candidate.after.agribalyse_code == "generic-yogurt"
    assert candidate.product_name == "Plain yogurt"


@pytest.mark.asyncio
async def test_unavailable_product_search_preserves_other_candidates(monkeypatch, catalogs):
    """A service error returns an explicit incomplete-search state instead of failing the dialog."""
    item = recipe()
    item.ingredients[0].barcode = "111"
    item.ingredients[0].ciqual_code = None
    monkeypatch.setattr(
        improvements, "product_candidates", AsyncMock(side_effect=OSError("offline"))
    )

    async def calculate(item):
        return result(item, green=60 if item.ingredients[1].ciqual_code == "19594" else 50)

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.unavailable
    assert [s.ingredient_id for s in response.suggestions] == ["second"]


@pytest.mark.asyncio
async def test_api_validation_and_conflict_response(monkeypatch):
    """Malformed drafts return 422; invalid selections return 409 without modifying inputs."""
    monkeypatch.setattr(improvements, "optimize_recipe", AsyncMock(side_effect=ValueError("stale")))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        invalid = await client.post("/v1/make-it-better/check", json={"recipe": {}})
        assert invalid.status_code == 422
        invalid = await client.post(
            "/v1/make-it-better/optimize",
            json={
                "recipe": recipe().model_dump(by_alias=True),
                "selected_ids": ["gone"],
            },
        )
        assert invalid.status_code == 409
    with pytest.raises(ValidationError):
        recipe(ingredients=[recipe().ingredients[0], recipe().ingredients[0]])


def test_unused_rows_do_not_invalidate_green_comparison():
    """A zero-quantity ingredient is absent from both scores rather than lost coverage."""
    item = recipe()
    item.ingredients[1].quantity_g = 0
    green, _, safe = improvements.score_changes(
        result(item, missing=["second"]), result(item, green=60, missing=["second"])
    )
    assert safe
    assert green.percent == 20


@pytest.mark.asyncio
async def test_local_swaps_survive_unavailable_off_search(monkeypatch, catalogs):
    """A row with both CIQUAL and OFF identities still receives its resolved food alternatives."""
    item = recipe(ingredients=[recipe().ingredients[0]])
    item.ingredients[0].barcode = "111"
    monkeypatch.setattr(
        improvements, "product_candidates", AsyncMock(side_effect=OSError("offline"))
    )

    async def calculate(item):
        return result(item, green=60 if item.ingredients[0].ciqual_code == "19594" else 50)

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.unavailable
    assert response.suggestions[0].category == "ingredient"


@pytest.mark.asyncio
async def test_discovered_yogurt_swap_uses_real_recipe_composition(monkeypatch):
    """Bundled CIQUAL foods must provide complete nutrients, with quantities used in the preview."""
    from api import recipe_analysis

    observed_sugars = []

    async def grade(nutrients, *_args, **_kwargs):
        observed_sugars.append(nutrients["sugars"])
        return nutriscore.NutriScore(
            grade="C",
            score=round(nutrients["sugars"]),
            components=nutriscore.ScoreComponents(positive=[], negative=[]),
        )

    monkeypatch.setattr(nutriscore, "calculate", grade)
    monkeypatch.setattr(
        recipe_analysis.score,
        "compute_green_score",
        AsyncMock(return_value=types.GreenScoreResponse(numeric_score=50, letter_grade="C")),
    )
    monkeypatch.setattr(
        improvements.agribalyse,
        "get_reference_rows",
        lambda: [
            {
                "code": "valid-green",
                "ciqual_code": "19594",
                "name_fr": "Yaourt nature",
                "score": 0.1,
            },
        ],
    )
    response = await improvements.find_improvements(
        improvements.ImprovementRequest(recipe=recipe())
    )
    assert len(response.suggestions) == 2
    assert observed_sugars[0] == pytest.approx(14.8)
    assert min(observed_sugars) < observed_sugars[0]
    assert response.suggestions[0].nutri_score.before == 15
    assert response.suggestions[0].nutri_score.after < 15


def test_partial_scores_compare_only_matching_exclusions():
    """Missing unrelated ingredients must not hide a measurable swap in the scored subset."""
    before = result(missing=["other"], status="partial")
    after = result(green=60, nutri=8, missing=["other"], status="partial")
    for report in (before, after):
        report[2].excluded_ingredients = [
            nutrition.ExcludedIngredient(
                ingredient_id="other",
                ingredient_name="Unresolved food",
                prepared_weight_g=50,
            )
        ]
    green, nutri, safe = improvements.score_changes(before, after)
    assert safe
    assert green.percent == 20 and green.excluded_count == 1
    assert nutri.percent == 20 and nutri.excluded_count == 1
    after[1].missing_ingredient_ids.append("first")
    assert not improvements.score_changes(before, after)[2]


@pytest.mark.asyncio
async def test_tradeoff_suggestion_can_be_selected(monkeypatch, catalogs):
    """Green OR nutrition improvements remain available with the other score's regression visible."""

    async def calculate(item):
        changed = any(row.ciqual_code == "19594" for row in item.ingredients)
        return result(item, green=60 if changed else 50, nutri=11 if changed else 10)

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    request = improvements.ImprovementRequest(recipe=recipe())
    response = await improvements.find_improvements(request)
    assert response.suggestions[0].green_score.percent == 20
    assert response.suggestions[0].nutri_score.percent == -10
    selected = await improvements.optimize_recipe(
        improvements.OptimizeRequest(
            recipe=request.recipe,
            selected_ids=[response.suggestions[0].id],
        )
    )
    assert selected.recipe.ingredients[0].ciqual_code == "19594"


@pytest.mark.asyncio
async def test_added_coverage_cannot_create_a_fake_percentage(monkeypatch):
    """Only originally scored rows are compared when a replacement resolves another row."""
    before = result(recipe(), missing=["second"])
    after = result(recipe(), green=90)
    calculator = AsyncMock(return_value=result(recipe(), green=55))
    monkeypatch.setattr(improvements, "calculate_report", calculator)
    green, _, safe = await improvements.compare_reports(before, after)
    assert safe
    assert green.percent == 10
    assert green.excluded_count == 1
    assert [r.id for r in calculator.call_args.args[0].ingredients] == ["first"]


@pytest.mark.asyncio
async def test_selected_swaps_with_different_coverage_changes_are_comparable(monkeypatch):
    """The combined preview uses each score's baseline subset, not its new denominator."""
    item = recipe()
    before = result(item, green=50, nutri=10, missing=["second"], status="partial")
    before[2].excluded_ingredients = [
        nutrition.ExcludedIngredient(
            ingredient_id="first",
            ingredient_name="Yogurt",
            prepared_weight_g=100,
        )
    ]
    after = result(item, green=90, nutri=4)

    async def calculate(subset):
        return result(subset, green=60, nutri=8)

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    green, nutri, safe = await improvements.compare_reports(before, after)
    assert safe
    assert green.percent == 20 and nutri.percent == 20
    assert green.excluded_count == 1 and nutri.excluded_count == 1


@pytest.mark.asyncio
async def test_empty_reasons_distinguish_no_candidates_and_unavailable_scores(monkeypatch):
    """An unsupported recipe is different from a supported alternative that cannot be graded."""
    item = recipe()
    for row in item.ingredients:
        row.ciqual_code = "unsupported"
    monkeypatch.setattr(improvements, "calculate_report", AsyncMock(return_value=result(item)))
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.reason == "no_candidates"
    item.ingredients[0].ciqual_code = "19580"
    suggestion = improvements.ImprovementSuggestion(
        id="first:ciqual:19594",
        ingredient_id="first",
        category="ingredient",
        before=item.ingredients[0],
        after=item.ingredients[0],
        green_score=None,
        nutri_score=None,
    )
    monkeypatch.setattr(improvements, "food_candidates", lambda *_: [suggestion])
    monkeypatch.setattr(
        improvements, "calculate_report", AsyncMock(return_value=(item, None, None))
    )
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.reason == "scores_unavailable"


@pytest.mark.asyncio
async def test_apple_pie_suggests_changes_with_real_green_algorithm(monkeypatch):
    """Apple pie gets verified catalog or quantity changes with the grade service offline."""
    from api import agribalyse, off, score, score_data
    from tests.helpers import create_taxonomy

    # Representative Agribalyse rows from the user's local catalog. The test is
    # self-contained: no downloaded taxonomy, Agribalyse file or OFF request.
    scores = {
        "23420": 0.416,
        "23424": 0.416,
        "13050": 0.0439,
        "16400": 0.768,
        "16410": 0.708,
        "31016": 0.126,
    }
    environmental = {
        code: {"code": code, "ciqual_code": code, "score": value, "name_fr": f"Food {code}"}
        for code, value in scores.items()
    }
    monkeypatch.setattr(agribalyse, "_agribalyse_by_code", environmental)
    monkeypatch.setattr(agribalyse, "_agribalyse_by_ciqual", environmental)
    monkeypatch.setattr(
        off, "get_ingredients_taxonomy", AsyncMock(return_value=create_taxonomy({}))
    )
    monkeypatch.setattr(off, "origins_by_country_code", AsyncMock(return_value={}))
    monkeypatch.setattr(off, "origin_to_country_origin", AsyncMock(return_value={}))
    monkeypatch.setattr(score, "labels_bonus_full", AsyncMock(return_value={}))
    monkeypatch.setattr(
        score, "labels_bonus_ingredients_restrictions_full", AsyncMock(return_value={})
    )
    monkeypatch.setattr(score_data, "get_epi_modifiers", AsyncMock(return_value={"en:world": -3}))
    monkeypatch.setattr(score_data, "get_distances_modifiers", AsyncMock(return_value={}))
    monkeypatch.setattr(nutriscore, "calculate", AsyncMock(side_effect=OSError("offline")))
    entries = [
        ("pastry", "puff pastry", "23420", 250),
        ("apples", "apples", "13396", 600),
        ("sugar", "sugar", "31016", 50),
        ("butter", "butter", "16400", 30),
    ]
    item = recipe(
        ingredients=[
            {
                "id": id_,
                "name": name,
                "quantity_g": weight,
                "ciqual_code": code,
                "agribalyse_code": code if code in environmental else None,
            }
            for id_, name, code, weight in entries
        ]
    )
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.suggestions
    suggestion = next(s for s in response.suggestions if s.green_score is not None)
    assert suggestion.green_score.after > suggestion.green_score.before
    assert suggestion.green_score.excluded_count == 1
    assert suggestion.nutri_score is None
    assert response.unavailable
    optimized = await improvements.optimize_recipe(
        improvements.OptimizeRequest(
            recipe=item,
            selected_ids=[suggestion.id],
        )
    )
    changed = next(
        row for row in optimized.recipe.ingredients if row.id == suggestion.ingredient_id
    )
    assert changed == suggestion.after
    assert optimized.recipe.ingredients[0].ciqual_code == "23420"


def test_catalog_discovery_preserves_culinary_role():
    """Search beyond reviewed pairs without exchanging fruit for dishes or cooked foods."""
    from api.improvement_candidates import compatible, discover_food_codes

    source = {"subgroup": "fruit", "name": "Pomme, crue"}
    assert compatible(source, {"subgroup": "fruit", "name": "Pomme, avec peau, crue"})
    assert not compatible(source, {"subgroup": "fruit", "name": "Pomme, cuite"})
    assert not compatible(source, {"subgroup": "dish", "name": "Pomme, crue"})
    assert not compatible(source, {"subgroup": "fruit", "name": "Poire, crue"})
    assert discover_food_codes("17270", {})  # an oil outside the reviewed list
    assert discover_food_codes("unknown", {}) == []


def test_quantity_candidates_are_modest_and_preserve_references():
    """Added sugar/oil reductions preserve identity and never target vegetables."""
    for code in ("31016", "17270"):
        row = recipe().ingredients[0].model_copy(update={"ciqual_code": code, "quantity_g": 50})
        candidates = improvements.food_candidates(row, "en")
        reductions = [item for item in candidates if ":quantity:" in item.id]
        assert [item.after.quantity_g for item in reductions] == [45, 40]
        assert all(item.after.ciqual_code == code for item in reductions)
        assert all(item.after.name == row.name for item in reductions)
    row = recipe().ingredients[0].model_copy(update={"ciqual_code": "13000"})
    assert not any(":quantity:" in item.id for item in improvements.food_candidates(row, "en"))
    row.prepared_weight_g = 80
    assert improvements.food_candidates(row, "en") == []


@pytest.mark.asyncio
async def test_quantity_change_is_verified_on_recipe_and_applied(monkeypatch):
    """A generic quantity candidate must improve the real comparison, then survive optimize."""
    item = recipe(
        ingredients=[{"id": "sugar", "name": "Sugar", "ciqual_code": "31016", "quantity_g": 50}]
    )

    async def calculate(current):
        return result(current, green=50, nutri=round(current.ingredients[0].quantity_g / 5))

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert len(response.suggestions) == 1
    suggestion = response.suggestions[0]
    assert suggestion.after.quantity_g == 40
    optimized = await improvements.optimize_recipe(
        improvements.OptimizeRequest(recipe=item, selected_ids=[suggestion.id])
    )
    assert optimized.recipe.ingredients[0].quantity_g == 40


@pytest.mark.asyncio
async def test_missing_ciqual_is_resolved_from_environmental_reference(monkeypatch, catalogs):
    """The dialog can discover alternatives before editor CIQUAL loading has finished."""
    monkeypatch.setattr(
        improvements.agribalyse,
        "get_reference_rows",
        lambda: [
            {"code": "chosen-green", "ciqual_code": "19594", "score": 0.1},
        ],
    )
    original = recipe(
        ingredients=[
            {"id": "row", "name": "Yogurt", "quantity_g": 100, "agribalyse_code": "chosen-green"}
        ]
    )
    resolved, unavailable = await improvements.resolve_recipe_references(original, "en")
    assert resolved.ingredients[0].ciqual_code == "19594"
    assert original.ingredients[0].ciqual_code is None
    assert not unavailable


@pytest.mark.asyncio
async def test_missing_references_are_resolved_from_taxonomy(monkeypatch):
    """Reuse established correspondence resolution and keep explicit choices intact."""
    from api.references import IngredientReferencesResponse, FoodReference

    lookup = AsyncMock(
        return_value=IngredientReferencesResponse(
            ciqual=FoodReference(code="16400", name="Butter"),
            agribalyse=FoodReference(code="16400", name="Butter"),
        )
    )
    monkeypatch.setattr(improvements.references, "ingredient_references", lookup)
    original = recipe(
        ingredients=[
            {
                "id": "butter",
                "name": "Butter",
                "quantity_g": 30,
                "codified_ingredient": {
                    "id": "en:butter",
                    "label": "Butter",
                    "is_in_taxonomy": True,
                },
            },
            {
                "id": "manual",
                "name": "Manual choice",
                "quantity_g": 100,
                "ciqual_code": "manual-code",
            },
            {"id": "unknown", "name": "Something", "quantity_g": 100},
        ]
    )
    resolved, unavailable = await improvements.resolve_recipe_references(original, "en")
    lookup.assert_awaited_once_with("en:butter", "en")
    assert resolved.ingredients[0].ciqual_code == "16400"
    assert resolved.ingredients[0].agribalyse_code == "16400"
    assert resolved.ingredients[1].ciqual_code == "manual-code"
    assert resolved.ingredients[2].ciqual_code is None
    assert not unavailable
    lookup.side_effect = OSError("offline")
    resolved, unavailable = await improvements.resolve_recipe_references(original, "en")
    assert unavailable and resolved.ingredients[0].ciqual_code is None


def test_catalog_discovers_butter_variants_without_a_swap_list():
    """Different fat levels in food names must not block matching the same base food."""
    from api.improvement_candidates import discover_food_codes

    assert "16410" in discover_food_codes("16400", {"16410": 0.708})
    assert not hasattr(improvements, "FOOD_SWAPS")


@pytest.mark.asyncio
async def test_unresolved_foods_have_an_actionable_empty_reason(monkeypatch):
    """Unknown free text cannot be scored by assigning a convenient replacement code."""
    monkeypatch.setattr(improvements, "calculate_report", AsyncMock(return_value=result()))
    item = recipe(ingredients=[{"id": "unknown", "name": "Unrecognized food", "quantity_g": 100}])
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert not response.suggestions
    assert response.reason == "references_missing"


@pytest.mark.asyncio
async def test_missing_editor_ciqual_does_not_hide_quantity_improvements(monkeypatch):
    """Resolve the baseline from the chosen environmental food and validate the same selection."""
    monkeypatch.setattr(
        improvements.agribalyse,
        "get_reference_rows",
        lambda: [
            {"code": "sugar-green", "ciqual_code": "31016", "score": 0.126},
        ],
    )

    async def calculate(current):
        assert current.ingredients[0].ciqual_code == "31016"
        return result(current, green=50, nutri=round(current.ingredients[0].quantity_g / 5))

    monkeypatch.setattr(improvements, "calculate_report", calculate)
    item = recipe(
        ingredients=[
            {"id": "sugar", "name": "Sugar", "quantity_g": 50, "agribalyse_code": "sugar-green"}
        ]
    )
    response = await improvements.find_improvements(improvements.ImprovementRequest(recipe=item))
    assert response.suggestions[0].after.quantity_g == 40
    optimized = await improvements.optimize_recipe(
        improvements.OptimizeRequest(
            recipe=item,
            selected_ids=[response.suggestions[0].id],
        )
    )
    assert optimized.recipe.ingredients[0].quantity_g == 40
    assert optimized.recipe.ingredients[0].ciqual_code == "31016"
    assert item.ingredients[0].ciqual_code is None
