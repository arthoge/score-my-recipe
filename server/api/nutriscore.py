"""Local Nutri-Score 2023 for the supported solid-recipe categories.

Adapted from Open Food Facts Product Opener (AGPL-3.0-or-later),
Copyright 2011-2026 Association Open Food Facts.
Pinned source: b1af9a0b17e3db046b088a4e04f8daebc2594772
https://github.com/openfoodfacts/openfoodfacts-server/blob/b1af9a0b17e3db046b088a4e04f8daebc2594772/lib/ProductOpener/Nutriscore.pm
Category preprocessing follows Food.pm at the same revision.
"""

import math

from pydantic import BaseModel


class ScoreComponent(BaseModel):
    """One favorable or unfavorable component returned by algorithm 2023."""

    id: str
    value: float | None = None
    unit: str = "g"
    points: int
    points_max: int


class ScoreComponents(BaseModel):
    """The components actually counted by the selected algorithm."""

    negative: list[ScoreComponent]
    positive: list[ScoreComponent]


class NutriScore(BaseModel):
    """Versioned algorithm result with the component explanations."""

    version: str = "2023"
    grade: str
    score: int
    components: ScoreComponents


# Values are compared before display rounding. Ratio thresholds alone are inclusive.
THRESHOLDS = {
    "energy": (335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350),
    "sugars": (3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51),
    "saturated_fat": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
    "salt": (
        0.2,
        0.4,
        0.6,
        0.8,
        1,
        1.2,
        1.4,
        1.6,
        1.8,
        2,
        2.2,
        2.4,
        2.6,
        2.8,
        3,
        3.2,
        3.4,
        3.6,
        3.8,
        4,
    ),
    "energy_from_saturated_fat": (120, 240, 360, 480, 600, 720, 840, 960, 1080, 1200),
    "saturated_fat_ratio": (10, 16, 22, 28, 34, 40, 46, 52, 58, 64),
    "fruits_vegetables_legumes": (40, 60, 80, 80, 80),
    "fiber": (3, 4.1, 5.2, 6.3, 7.4),
    "proteins": (2.4, 4.8, 7.2, 9.6, 12, 14, 17),
}


def _component(name: str, value: float, red_meat: bool) -> ScoreComponent:
    """Apply the published thresholds; round only the displayed component value."""
    thresholds = THRESHOLDS[name]
    points = sum(
        value >= limit if name == "saturated_fat_ratio" else value > limit for limit in thresholds
    )
    if name == "proteins" and red_meat:
        points = min(points, 2)
    unit = (
        "kJ"
        if name.startswith("energy")
        else "%"
        if name in ("fruits_vegetables_legumes", "saturated_fat_ratio")
        else "g"
    )
    return ScoreComponent(
        id=name, value=round(value, 2), unit=unit, points=points, points_max=len(thresholds)
    )


async def calculate(
    nutrients: dict[str, float],
    plant_percent: float,
    category: str = "en:meals",
    red_meat_percent: float = 0,
) -> NutriScore:
    """Compute a new score without network access or reusing a previous recipe's grade.

    The async interface is shared with the composition pipeline. Beverages remain
    unsupported there because recipe grams do not establish volume or sweeteners.
    Missing nutrients must be excluded/fallback-resolved by that pipeline first.
    """
    if category not in ("en:meals", "en:cheeses", "en:fats"):
        raise ValueError("Unsupported recipe category")
    required = ("energy_kj", "saturated_fat", "sugars", "salt", "fiber", "proteins", "fat")
    if any(
        key not in nutrients or not math.isfinite(nutrients[key]) or nutrients[key] < 0
        for key in required
    ):
        raise ValueError("Complete finite nonnegative nutrient inputs are required")
    if any(
        not math.isfinite(value) or not -1e-9 <= value <= 100 + 1e-9
        for value in (plant_percent, red_meat_percent)
    ):
        raise ValueError("Ingredient percentages must be between 0 and 100")
    # Weighted sums can exceed the endpoints by floating-point round-off.
    plant_percent = min(100, max(0, plant_percent))
    red_meat_percent = min(100, max(0, red_meat_percent))
    fats = category == "en:fats"
    values = {
        **nutrients,
        "energy": nutrients["energy_kj"],
        "fruits_vegetables_legumes": plant_percent,
    }
    energy, saturates = "energy", "saturated_fat"
    if fats:
        energy, saturates = "energy_from_saturated_fat", "saturated_fat_ratio"
        values[energy] = nutrients["saturated_fat"] * 37
        # OFF Food.pm rounds the ratio to one decimal before applying thresholds.
        values[saturates] = (
            round(
                nutrients["saturated_fat"] / (nutrients["fat"] or nutrients["saturated_fat"]) * 100,
                1,
            )
            if nutrients["saturated_fat"]
            else 0
        )
    negative = [
        _component(key, values[key], False) for key in (energy, "sugars", saturates, "salt")
    ]
    negative_points = sum(part.points for part in negative)
    positive_keys = ["fiber", "fruits_vegetables_legumes"]
    if category == "en:cheeses" or negative_points < (7 if fats else 11):
        positive_keys.insert(0, "proteins")
    # OFF Food.pm defines a red-meat product as more than 10% red meat.
    positive = [_component(key, values[key], red_meat_percent > 10) for key in positive_keys]
    score = negative_points - sum(part.points for part in positive)
    limits = (-6 if fats else 0, 2, 10, 18)
    grade = "ABCDE"[sum(score > limit for limit in limits)]
    return NutriScore(
        grade=grade, score=score, components=ScoreComponents(negative=negative, positive=positive)
    )
