"""Catalog-backed product improvement recommendations for recipes."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import api.types as types


CATALOG_PATH = Path(__file__).resolve().parent / "make_it_better_catalog.json"
SCORE_VALUES = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}


def normalize_name(value: str) -> str:
    """Return a case- and accent-insensitive name suitable for catalog lookup."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    """Load the explicit catalog and reject malformed top-level data."""
    with path.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)
    if not isinstance(catalog, list):
        raise RuntimeError("The improvement catalog must contain a JSON array.")
    return catalog


def find_improvements(ingredients: list[str]) -> types.MakeItBetterResponse:
    """Return the highest combined score improvement for each known ingredient.

    The local catalog deliberately offers only declared alternatives. This keeps
    recommendations deterministic and avoids inferring product-level scores.
    """
    catalog = load_catalog()
    products_by_id = {product["id"]: product for product in catalog}
    products_by_alias = {
        normalize_name(alias): product
        for product in catalog
        for alias in product.get("aliases", [])
    }
    suggestions: list[types.MakeItBetterSuggestion] = []
    no_improvement: list[str] = []

    for ingredient in ingredients:
        source = products_by_alias.get(normalize_name(ingredient))
        if source is None:
            no_improvement.append(ingredient)
            continue

        options: list[tuple[int, dict[str, Any], list[types.ScoreImprovement]]] = []
        for candidate_id in source.get("better_options", []):
            candidate = products_by_id.get(candidate_id)
            if candidate is None:
                raise RuntimeError(f"Unknown improvement option: {candidate_id}")
            improvements = [
                types.ScoreImprovement(label=label, from_score=source[field], to_score=candidate[field])
                for field, label in (("nutri_score", "Nutri-Score"), ("green_score", "Green-Score"))
                if SCORE_VALUES[candidate[field]] > SCORE_VALUES[source[field]]
            ]
            if improvements:
                gain = sum(
                    SCORE_VALUES[improvement.to_score] - SCORE_VALUES[improvement.from_score]
                    for improvement in improvements
                )
                options.append((gain, candidate, improvements))

        if not options:
            no_improvement.append(ingredient)
            continue

        _, candidate, improvements = max(options, key=lambda option: (option[0], option[1]["id"]))
        suggestions.append(
            types.MakeItBetterSuggestion(
                ingredient=ingredient,
                original=types.ImprovementProduct(
                    id=source["id"],
                    name=source["name"],
                    nutri_score=source["nutri_score"],
                    green_score=source["green_score"],
                ),
                suggested=types.ImprovementProduct(
                    id=candidate["id"],
                    name=candidate["name"],
                    nutri_score=candidate["nutri_score"],
                    green_score=candidate["green_score"],
                ),
                improvements=improvements,
            )
        )

    return types.MakeItBetterResponse(suggestions=suggestions, no_improvement=no_improvement)
