"""Recipe-scanning API backed exclusively by the local Open Food Facts fixtures.

The service deliberately distinguishes taxonomy matches from environmental
claims: the bundled JSON files do not contain product-level eco scores.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


DATA_DIRECTORY = Path(__file__).resolve().parent
INGREDIENTS_FILE = DATA_DIRECTORY / "ingredients.full.json"
LABELS_FILE = DATA_DIRECTORY / "labels.full.json"
IMPROVEMENT_CATALOG_FILE = DATA_DIRECTORY / "make_it_better_catalog.json"
SCORE_VALUES = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}

# This is intentionally a small, explicit rule. It only proposes an option
# that exists in the local taxonomy; it is not an unsubstantiated eco-score.
SUSTAINABLE_ALTERNATIVES = {
    "en:red-wine": {
        "ingredient_id": "en:organic-red-wine",
        "reason": "A certified organic red-wine option exists in the local taxonomy.",
    }
}


class RecipeScanRequest(BaseModel):
    """Payload used to identify the ingredient names in one recipe."""

    ingredients: list[str] = Field(min_length=1, max_length=100)
    language: str = Field(default="en", min_length=2, max_length=10)


class MakeItBetterRequest(BaseModel):
    """Product rows submitted by the main ingredient table."""

    ingredients: list[str] = Field(min_length=1, max_length=100)
    language: str = Field(default="es", min_length=2, max_length=10)


def normalize(value: str) -> str:
    """Return a case- and accent-insensitive lookup key for a food name."""

    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def load_json(path: Path) -> dict[str, dict[str, Any]]:
    """Load one local taxonomy file and reject unexpected top-level JSON data."""

    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name} must contain a JSON object at its top level.")
    return data


def load_improvement_catalog(path: Path) -> list[dict[str, Any]]:
    """Load product scores and the allowed suggestions for Make it better."""

    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise RuntimeError(f"{path.name} must contain a JSON array at its top level.")
    for product in data:
        if not isinstance(product, dict) or not isinstance(product.get("id"), str):
            raise RuntimeError(f"{path.name} contains a product without a string id.")
    return data


def validate_relationships(ingredients: dict[str, dict[str, Any]]) -> None:
    """Ensure every parent and child taxonomy reference resolves locally."""

    for ingredient_id, ingredient in ingredients.items():
        for relation in ("parents", "children"):
            for target_id in ingredient.get(relation) or []:
                if target_id not in ingredients:
                    raise RuntimeError(
                        f"{ingredient_id} has an unresolved {relation} reference: {target_id}"
                    )


def iter_aliases(ingredient_id: str, ingredient: dict[str, Any]) -> Iterable[str]:
    """Yield all local identifiers and translated names usable for matching."""

    yield ingredient_id
    yield ingredient_id.split(":", maxsplit=1)[-1].replace("-", " ")
    for name in ingredient.get("name", {}).values():
        if isinstance(name, str):
            yield name
    for names in ingredient.get("synonyms", {}).values():
        if isinstance(names, list):
            yield from (name for name in names if isinstance(name, str))


class TaxonomyStore:
    """Read-only, validated access to the ingredient and label fixtures."""

    def __init__(self) -> None:
        """Load the two fixtures once while constructing the application store."""

        self.ingredients = load_json(INGREDIENTS_FILE)
        self.labels = load_json(LABELS_FILE)
        self.improvement_products = load_improvement_catalog(IMPROVEMENT_CATALOG_FILE)
        validate_relationships(self.ingredients)
        self.aliases = self._build_aliases()
        self.product_aliases = self._build_product_aliases()

    def _build_aliases(self) -> dict[str, list[str]]:
        """Build a normalized alias index without silently choosing ambiguous names."""

        aliases: dict[str, list[str]] = {}
        for ingredient_id, ingredient in self.ingredients.items():
            for alias in iter_aliases(ingredient_id, ingredient):
                key = normalize(alias)
                if key:
                    aliases.setdefault(key, []).append(ingredient_id)
        return aliases

    def _build_product_aliases(self) -> dict[str, dict[str, Any]]:
        """Index explicit product aliases, avoiding guesses based on a food type."""

        aliases: dict[str, dict[str, Any]] = {}
        for product in self.improvement_products:
            for alias in product.get("aliases", []):
                key = normalize(alias)
                if key in aliases:
                    raise RuntimeError(f"Ambiguous product alias in {IMPROVEMENT_CATALOG_FILE.name}: {alias}")
                aliases[key] = product
        return aliases

    def resolve(self, query: str) -> tuple[str | None, list[str]]:
        """Resolve one query, returning candidates when the name is ambiguous."""

        candidates = sorted(set(self.aliases.get(normalize(query), [])))
        return (candidates[0], []) if len(candidates) == 1 else (None, candidates)

    def display_name(self, ingredient_id: str, language: str) -> str:
        """Return a requested translation, falling back to English and then the ID."""

        names = self.ingredients[ingredient_id].get("name", {})
        return names.get(language) or names.get("en") or next(iter(names.values()), ingredient_id)

    def ancestors(self, ingredient_id: str) -> set[str]:
        """Return the complete parent chain for a valid local ingredient node."""

        found: set[str] = set()
        pending = list(self.ingredients[ingredient_id].get("parents") or [])
        while pending:
            parent_id = pending.pop()
            if parent_id not in found:
                found.add(parent_id)
                pending.extend(self.ingredients[parent_id].get("parents") or [])
        return found


store = TaxonomyStore()
app = FastAPI(title="Score My Recipe local scanner", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# A deliberately small visual client for trying the Make it better flow.
# The application that owns the real recipe/PDF UI can call the same endpoint.
app.mount("/demo", StaticFiles(directory=DATA_DIRECTORY / "frontend-demo", html=True), name="demo")


@app.get("/health")
def health() -> dict[str, int | str]:
    """Report that the API started and both local taxonomies were validated."""

    return {
        "status": "ok",
        "ingredients": len(store.ingredients),
        "labels": len(store.labels),
        "improvement_products": len(store.improvement_products),
    }


@app.get("/labels/search")
def search_labels(query: str = Query(min_length=1), language: str = "en") -> list[dict[str, str]]:
    """Search sustainable-certification labels by localized name or synonym."""

    search_key = normalize(query)
    results = []
    for label_id, label in store.labels.items():
        aliases = [label_id, *label.get("name", {}).values()]
        aliases.extend(name for names in label.get("synonyms", {}).values() for name in names)
        if any(search_key in normalize(alias) for alias in aliases if isinstance(alias, str)):
            names = label.get("name", {})
            results.append({"id": label_id, "name": names.get(language) or names.get("en") or label_id})
    return results


@app.post("/scan-recipe")
def scan_recipe(recipe: RecipeScanRequest) -> dict[str, Any]:
    """Match recipe ingredients and return only taxonomy-backed alternatives."""

    matches: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    recommendations: list[dict[str, str]] = []
    for query in recipe.ingredients:
        ingredient_id, candidates = store.resolve(query)
        if candidates:
            unresolved.append({"ingredient": query, "candidates": candidates})
            continue
        if ingredient_id is None:
            unresolved.append({"ingredient": query, "candidates": []})
            continue
        matches.append(
            {
                "ingredient": query,
                "id": ingredient_id,
                "name": store.display_name(ingredient_id, recipe.language),
                "parents": sorted(store.ancestors(ingredient_id)),
            }
        )
        alternative = SUSTAINABLE_ALTERNATIVES.get(ingredient_id)
        if alternative:
            recommendations.append(
                {
                    "replace": ingredient_id,
                    "with": alternative["ingredient_id"],
                    "name": store.display_name(alternative["ingredient_id"], recipe.language),
                    "reason": alternative["reason"],
                }
            )
    return {
        "matched_ingredients": matches,
        "unresolved_ingredients": unresolved,
        "recommendations": recommendations,
        "notice": "Recommendations are taxonomy and certification hints, not verified product-level environmental scores.",
    }


def score_improvements(source: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only score dimensions that improve from source to candidate."""

    improvements = []
    for field, label in (("nutri_score", "Nutri-Score"), ("green_score", "Green-Score")):
        before = source[field]
        after = candidate[field]
        gain = SCORE_VALUES[after] - SCORE_VALUES[before]
        if gain > 0:
            improvements.append({"score": field, "label": label, "from": before, "to": after, "gain": gain})
    return improvements


@app.post("/make-it-better/check")
def check_make_it_better(recipe: MakeItBetterRequest) -> dict[str, Any]:
    """Find the strongest Nutri-Score/Green-Score upgrade for each known row."""

    by_id = {product["id"]: product for product in store.improvement_products}
    suggestions: list[dict[str, Any]] = []
    no_improvement: list[str] = []
    for ingredient in recipe.ingredients:
        source = store.product_aliases.get(normalize(ingredient))
        if source is None:
            no_improvement.append(ingredient)
            continue
        options = []
        for candidate_id in source.get("better_options", []):
            candidate = by_id.get(candidate_id)
            if candidate is None:
                raise RuntimeError(f"{source['id']} references an unknown improvement option.")
            improvements = score_improvements(source, candidate)
            if improvements:
                options.append((sum(item["gain"] for item in improvements), candidate, improvements))
        if not options:
            no_improvement.append(ingredient)
            continue
        # One suggestion only: choose the largest combined score gain.  The id
        # makes ties deterministic, so the same input always gets the same UI.
        _, candidate, improvements = max(options, key=lambda option: (option[0], option[1]["id"]))
        suggestions.append(
            {
                "ingredient": ingredient,
                "original": {"id": source["id"], "name": source["name"], "nutri_score": source["nutri_score"], "green_score": source["green_score"]},
                "suggested": {"id": candidate["id"], "name": candidate["name"], "nutri_score": candidate["nutri_score"], "green_score": candidate["green_score"]},
                "improvements": improvements,
            }
        )
    return {
        "suggestions": suggestions,
        "no_improvement": no_improvement,
        "notice": "Solo se sugieren cambios que mejoran Nutri-Score, Green-Score o ambos según el catálogo local.",
    }


@app.get("/ingredients/{ingredient_id}")
def get_ingredient(ingredient_id: str, language: str = "en") -> dict[str, Any]:
    """Return one canonical local taxonomy ingredient with a localized name."""

    if ingredient_id not in store.ingredients:
        raise HTTPException(status_code=404, detail="Ingredient not found in the local fixture.")
    return {"id": ingredient_id, "name": store.display_name(ingredient_id, language), **store.ingredients[ingredient_id]}
