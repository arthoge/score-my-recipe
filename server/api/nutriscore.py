"""Non-persisting OFF algorithm-2023 adapter, cached by exact calculation inputs."""

import json
import urllib.request

from async_lru import alru_cache
from pydantic import BaseModel

from api.nutrition_data import fetch_json
from api.off import USER_AGENT

TEST_URL = "https://world.openfoodfacts.org/api/v3.6/product/test"


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
    """Versioned algorithm result with the upstream component explanations."""

    version: str = "2023"
    grade: str
    score: int
    components: ScoreComponents


def calculation_payload(
    nutrients: dict[str, float], plant_percent: float, category: str, red_meat_percent: float = 0
) -> dict:
    """Send structured nutrition for a complete served component, without a barcode.

    OFF's reserved source 'estimate' is recomputed from ingredient text. Use our
    own source so recipe totals survive that upstream estimation step.
    """
    names = {"energy_kj": "energy-kj", "saturated_fat": "saturated-fat"}
    values = {
        names.get(key, key): {
            "value_string": str(value),
            "unit": "kJ" if key == "energy_kj" else "g",
        }
        for key, value in nutrients.items()
    }
    values["fruits-vegetables-legumes"] = {"value_string": str(plant_percent), "unit": "%"}
    return {
        "lc": "en",
        "fields": "nutriscore",
        "product": {
            "lang": "en",
            # OFF recognizes quantified beef as red meat and applies the 2023 protein cap.
            # This synthetic text conveys only red-meat proportion; the plant proportion
            # is supplied explicitly in the nutrient input set above.
            "ingredients_text_en": f"beef ({red_meat_percent}%), other ingredients ({100 - red_meat_percent}%)",
            "categories_tags": [category],
            "nutrition": {
                "input_sets": [
                    {
                        "source": "recipe-composition",
                        "preparation": "as_sold",
                        "per": "100g",
                        "nutrients": values,
                    }
                ]
            },
        },
    }


def parse_result(data: dict) -> NutriScore:
    """Accept only a verified 2023 result; never fall back to the old algorithm."""
    if data.get("errors") or data.get("status") not in ("success", "success_with_warnings"):
        raise ValueError("OFF rejected recipe calculation inputs")
    result = data.get("product", {}).get("nutriscore", {}).get("2023", {})
    grade, score = result.get("grade"), result.get("score")
    components = result.get("data", {}).get("components")
    if grade not in ("a", "b", "c", "d", "e") or type(score) is not int:
        raise ValueError("OFF returned no algorithm-2023 grade")
    if not isinstance(components, dict):
        raise ValueError("OFF returned no algorithm-2023 components")
    return NutriScore(grade=grade.upper(), score=score, components=components)


@alru_cache(maxsize=128, ttl=3600)
async def _calculate(payload: str) -> NutriScore:
    """Cache successful exact-input calculations; failures are not cached."""
    request = urllib.request.Request(
        TEST_URL,
        data=payload.encode(),
        method="PATCH",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    return parse_result(await fetch_json(request))


async def calculate(
    nutrients: dict[str, float],
    plant_percent: float,
    category: str = "en:meals",
    red_meat_percent: float = 0,
) -> NutriScore:
    """Calculate one complete recipe in OFF's documented non-persisting test mode."""
    payload = calculation_payload(nutrients, plant_percent, category, red_meat_percent)
    return await _calculate(json.dumps(payload, sort_keys=True, separators=(",", ":")))
