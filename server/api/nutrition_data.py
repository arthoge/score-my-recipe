"""Versioned nutrient composition and bounded, cached OFF product lookups."""

import asyncio
import hashlib
import io
import json
import math
from functools import lru_cache
from pathlib import Path
import urllib.error
import urllib.request

from async_lru import alru_cache
import openpyxl

from api.off import USER_AGENT

CATALOG_PATH = Path(__file__).parent / "resources" / "ciqual-nutrients-2025.json"
SOURCE_URL = "https://entrepot.recherche.data.gouv.fr/api/access/datafile/666260"
SOURCE_SHA256 = "5555c572fa3735991298d832d0427788fa69a11b4fd20a5d580d58942369fbb0"
# Pinned column indices in the official 2025 workbook, checked against their headings.
COLUMNS = {
    "energy_kj": (9, "Energie"),
    "proteins": (15, "Protéines"),
    "carbohydrates": (16, "Glucides"),
    "fat": (17, "Lipides"),
    "sugars": (18, "Sucres"),
    "fiber": (26, "Fibres"),
    "saturated_fat": (31, "AG"),
    "salt": (49, "Sel"),
}


def write_catalog(workbook: bytes, target: Path = CATALOG_PATH) -> None:
    """Extract required nutrients, retaining missing/trace/less-than source values verbatim."""
    if hashlib.sha256(workbook).hexdigest() != SOURCE_SHA256:
        raise ValueError("CIQUAL nutrition checksum differs from the pinned 2025 release")
    book = openpyxl.load_workbook(io.BytesIO(workbook), read_only=True, data_only=True)
    rows = iter(book["composition nutritionnelle"].values)
    headings = next(rows)
    for index, prefix in COLUMNS.values():
        if not str(headings[index]).startswith(prefix):
            raise ValueError("CIQUAL nutrition columns changed")
    foods = {}
    for row in rows:
        code = str(row[6]).strip()
        if code in foods:
            raise ValueError("Duplicate CIQUAL nutrition food")
        foods[code] = {
            "name": str(row[7]).replace("\n", " "),
            "group": str(row[0]),
            "subgroup": str(row[1]),
            "detail_group": str(row[2]),
            "nutrients": {key: row[index] for key, (index, _) in COLUMNS.items()},
        }
    book.close()
    target.write_text(
        json.dumps(
            {"version": "2025", "source": SOURCE_URL, "sha256": SOURCE_SHA256, "foods": foods},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    get_foods.cache_clear()


def fetch_catalog(target: Path = CATALOG_PATH) -> None:
    """Rebuild nutrition data from the pinned official ANSES workbook."""
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        write_catalog(response.read(), target)


@lru_cache(maxsize=1)
def get_foods() -> dict:
    """Load the bundled composition without a runtime download."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["foods"]


def nutrient_value(raw: object, favorable: bool = False) -> tuple[float | None, bool]:
    """Return a conservative bound for quantified limits; missing and traces stay unknown.

    A '< x' value lies between zero and x. Use zero for favorable nutrients and x
    for unfavorable ones, with an explicit bound warning. 'Traces' has no numeric
    upper bound, so it cannot be silently treated as an analytical zero.
    """
    text = str(raw).strip().replace(",", ".")
    limited = text.startswith("<")
    try:
        value = float(text.lstrip("< "))
    except (ValueError, TypeError):
        return None, False
    if not math.isfinite(value) or value < 0:
        return None, False
    return (0 if favorable and limited else value), limited


async def fetch_json(request: urllib.request.Request) -> dict:
    """Bound upstream network time and keep blocking HTTP work off the event loop."""

    def read() -> dict:
        """Decode one upstream response, limiting its size."""
        with urllib.request.urlopen(request, timeout=10) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Upstream response too large")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError("Invalid upstream response")
        return result

    return await asyncio.to_thread(read)


@alru_cache(maxsize=128, ttl=3600)
async def get_product(barcode: str) -> dict | None:
    """Read nutrition for an identified product; never substitute another barcode."""
    if not barcode.isdigit() or not 1 <= len(barcode) <= 24:
        return None
    url = (
        f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        "?fields=code,product_name,nutriments,ingredients,categories_tags,nutrition_data_per,nutriscore,additives_tags,allergens_tags"
    )
    try:
        data = await fetch_json(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    product = data.get("product")
    return product if isinstance(product, dict) else None
