"""Discover conservative alternatives from bundled food identities and composition."""

import re

from api import ciqual, nutrition_data

PREPARATION_TERMS = (
    "cru",
    "cuit",
    "seche",
    "poudre",
    "appertise",
    "surgele",
    "egoutte",
    "frit",
)


def compatible(source: dict, target: dict) -> bool:
    """Keep the food's culinary role and preparation instead of matching broad groups."""
    if source.get("subgroup") != target.get("subgroup") or not source.get("subgroup"):
        return False
    old, new = (ciqual.normalize(item.get("name", "")) for item in (source, target))
    if not old or not new:
        return False
    if any((term in old) != (term in new) for term in PREPARATION_TERMS):
        return False
    source_detail, target_detail = source.get("detail_group"), target.get("detail_group")
    if source_detail not in (None, "000000") and source_detail != target_detail:
        return False

    # Compare the leading food nouns, dropping descriptors such as fat percentage.
    # This discovers butter/milk/yogurt variants without a list of food codes.
    def base(name: str) -> str:
        head = name.split(",")[0]
        return re.split(r"\s+(?:a|au|aux|ou|de|d')\s*", head, maxsplit=1)[0]

    return base(old) == base(new)


def nutrient_priority(source: dict, target: dict) -> float:
    """Shortlist composition differences; only recipe simulations establish improvements."""
    total = 0.0
    for nutrient, direction in (
        ("saturated_fat", -1),
        ("sugars", -1),
        ("salt", -1),
        ("fiber", 1),
    ):
        old, _ = nutrition_data.nutrient_value(source.get("nutrients", {}).get(nutrient))
        new, _ = nutrition_data.nutrient_value(target.get("nutrients", {}).get(nutrient))
        if old is not None and new is not None:
            total += direction * (new - old) / max(old, 1)
    return total


def discover_food_codes(code: str | None, environmental: dict[str, float]) -> list[str]:
    """Take candidates for nutrition and environment separately to retain both objectives."""
    foods = nutrition_data.get_foods()
    source = foods.get(code)
    if not source:
        return []
    candidates = [
        key
        for key, food in foods.items()
        if key != code and key in ciqual.get_foods() and compatible(source, food)
    ]
    nutrition = sorted(candidates, key=lambda key: (-nutrient_priority(source, foods[key]), key))
    green = sorted(
        (key for key in candidates if key in environmental),
        key=lambda key: (environmental[key], key),
    )
    return list(dict.fromkeys(nutrition[:2] + green[:2]))
