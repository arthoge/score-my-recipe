"""Automated checks for the local Score My Recipe API."""

import sys
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

# The API lives one directory above this conventional test package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import MakeItBetterRequest, RecipeScanRequest, app, check_make_it_better, get_ingredient, health, scan_recipe, store, validate_relationships


def test_all_fixture_relationships_resolve() -> None:
    """The reduced ingredient fixture must never contain dangling references."""

    validate_relationships(store.ingredients)


def test_health_reports_loaded_taxonomies() -> None:
    """The health route exposes the counts after startup validation."""

    assert health() == {"status": "ok", "ingredients": 20, "labels": 26, "improvement_products": 3}
    paths = {route.path for route in app.routes}
    assert "/scan-recipe" in paths
    assert "/demo" in paths


def test_recipe_scan_matches_spanish_and_recommends_organic_wine() -> None:
    """A mixed-language recipe resolves known food and preserves unknown input."""

    payload = scan_recipe(
        RecipeScanRequest(ingredients=["pera", "red wine", "mystery powder"], language="es")
    )

    assert [item["id"] for item in payload["matched_ingredients"]] == ["en:pear", "en:red-wine"]
    assert payload["unresolved_ingredients"] == [{"ingredient": "mystery powder", "candidates": []}]
    assert payload["recommendations"][0]["with"] == "en:organic-red-wine"


def test_unknown_ingredient_endpoint_returns_404() -> None:
    """Unknown canonical IDs return a useful HTTP status instead of a server error."""

    try:
        get_ingredient("en:not-present")
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("Unknown ingredients must raise HTTPException(404).")


def test_recipe_request_requires_at_least_one_ingredient() -> None:
    """An empty recipe is rejected before the scanner starts processing it."""

    try:
        RecipeScanRequest(ingredients=[])
    except ValidationError:
        return
    raise AssertionError("Empty ingredient lists must fail request validation.")


def test_make_it_better_selects_the_best_score_improvement() -> None:
    """The check chooses one candidate with the strongest combined score gain."""

    payload = check_make_it_better(MakeItBetterRequest(ingredients=["yogur de chocolate", "tomate"]))

    suggestion = payload["suggestions"][0]
    assert suggestion["suggested"]["name"] == "Yogur natural ecológico"
    assert [(item["from"], item["to"]) for item in suggestion["improvements"]] == [("D", "A"), ("D", "A")]
    assert payload["no_improvement"] == ["tomate"]
