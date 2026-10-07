"""Prepared-mass estimates from narrowly matched, versioned cooking-yield profiles.

These estimates concern weight only. They do not establish nutrient retention,
select a prepared nutrition reference, or change the existing Green Score.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Preparation = Literal[
    "none", "boiled", "steamed", "baked_roasted", "grilled", "pan_fried", "deep_fried"
]


class PreparedWeightRequest(BaseModel):
    """Edible quantity and explicit food identity before the selected preparation."""

    quantity_g: float = Field(gt=0, allow_inf_nan=False)
    state: Literal["raw", "cooked", "drained"] = "raw"
    preparation: Preparation = "none"
    ciqual_code: str | None = None
    barcode: str | None = None


class YieldSource(BaseModel):
    """Traceable source and conditions for an estimated prepared mass."""

    version: str
    url: str
    table: str
    food: str
    conditions: str


class PreparedWeightResponse(BaseModel):
    """Unsupported transformations retain the entered quantity without a documented yield."""

    status: Literal["unchanged", "estimated", "unsupported"]
    prepared_weight_g: float | None = None
    yield_factor: float | None = None
    profile_id: str | None = None
    source: YieldSource | None = None


@lru_cache(maxsize=1)
def get_yield_catalog() -> dict:
    """Load the local, reviewed yield catalogue without any runtime network requests."""
    path = Path(__file__).parent / "resources" / "preparation-yields-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_prepared_weight(request: PreparedWeightRequest) -> PreparedWeightResponse:
    """Apply one yield to raw edible mass; already prepared weights are never converted twice."""
    if request.state in ("cooked", "drained") or request.preparation == "none":
        return PreparedWeightResponse(
            status="unchanged", prepared_weight_g=request.quantity_g, yield_factor=1
        )
    # The selected CIQUAL food defines the cooking yield independently of an OFF
    # nutrition reference. A barcode alone provides no documented cooking profile.
    catalog = get_yield_catalog()
    for profile in catalog["profiles"]:
        if (
            request.ciqual_code in profile["ciqual_codes"]
            and request.preparation == profile["preparation"]
        ):
            return PreparedWeightResponse(
                status="estimated",
                prepared_weight_g=round(request.quantity_g * profile["factor"], 2),
                yield_factor=profile["factor"],
                profile_id=profile["id"],
                source=YieldSource(
                    version=catalog["version"],
                    url=catalog["source"],
                    table=profile["source_table"],
                    food=profile["source_food"],
                    conditions=profile["conditions"],
                ),
            )
    return PreparedWeightResponse(status="unsupported", prepared_weight_g=request.quantity_g)
