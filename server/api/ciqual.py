"""Versioned ANSES CIQUAL food identities, independent from environmental references."""

from functools import lru_cache
from pathlib import Path
from difflib import SequenceMatcher
import hashlib
import json
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

CATALOG_PATH = Path(__file__).parent / "resources" / "ciqual-foods-2025.json"
SOURCE_URL = "https://entrepot.recherche.data.gouv.fr/api/access/datafile/666252"
SOURCE_SHA256 = "e0b1de25b3039028205e9d54a96892e403e1b313c2efeb41180fabe132627478"


def parse_foods(xml: bytes) -> list[dict[str, str]]:
    """Read official food codes and bilingual names, without substituting Agribalyse names."""
    foods = []
    codes = set()
    for element in ET.fromstring(xml).findall("ALIM"):
        food = {
            "code": (element.findtext("alim_code") or "").strip(),
            "name_fr": (element.findtext("alim_nom_fr") or "").strip(),
            "name_en": (element.findtext("alim_nom_eng") or "").strip(),
        }
        if not food["code"] or not food["name_fr"] or food["code"] in codes:
            raise ValueError("CIQUAL food codes must be unique and have a French name")
        codes.add(food["code"])
        foods.append(food)
    if not foods:
        raise ValueError("CIQUAL source contains no foods")
    return foods


def write_catalog(xml: bytes, target: Path) -> None:
    """Generate a reproducible food catalog from the pinned official XML release."""
    if hashlib.sha256(xml).hexdigest() != SOURCE_SHA256:
        raise ValueError("CIQUAL source checksum differs from the pinned 2025 release")
    foods = parse_foods(xml)
    target.parent.mkdir(parents=True, exist_ok=True)
    records = ",\n".join("    " + json.dumps(food, ensure_ascii=False) for food in foods)
    target.write_text(
        '{\n  "version": "2025",\n  "source": '
        + json.dumps(SOURCE_URL)
        + ',\n  "sha256": '
        + json.dumps(SOURCE_SHA256)
        + ',\n  "foods": [\n'
        + records
        + "\n  ]\n}\n",
        encoding="utf-8",
    )
    get_foods.cache_clear()


def fetch_catalog(target: Path = CATALOG_PATH) -> None:
    """Download the pinned ANSES food list and regenerate the bundled catalog."""
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        write_catalog(response.read(), target)


@lru_cache(maxsize=1)
def get_foods() -> dict[str, dict[str, str]]:
    """Load bundled identities once; application startup needs no external download."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {food["code"]: food for food in data["foods"]}


def food_name(food: dict[str, str], lang: str) -> str:
    """Use the official English or French name, falling back to French for other locales."""
    return food["name_en"] if lang.startswith("en") and food["name_en"] else food["name_fr"]


def normalize(text: str) -> str:
    """Compare food names independent of accents and case."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.strip().lower())
        if not unicodedata.combining(char)
    )


def search_foods(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Search both official languages, keeping distinct raw, cooked and drained foods."""
    needle = normalize(query)
    if not needle:
        return []
    matches = []
    for food in get_foods().values():
        names = [normalize(food[key]) for key in ("name_fr", "name_en")]
        rank = max(_match_rank(needle, name) for name in names)
        if rank >= 0.45:
            matches.append((rank, food))
    matches.sort(key=lambda item: (-item[0], item[1]["code"]))
    return [food for _, food in matches[:limit]]


def _match_rank(needle: str, name: str) -> float:
    """Prefer a food named by the query over composite dishes containing that ingredient."""
    if needle == name:
        return 1.0
    similarity = SequenceMatcher(None, needle, name).ratio()
    if name.startswith(needle + ","):
        return 0.95 + similarity * 0.04 + (0.03 if "(average)" in name else 0)
    if name.startswith(needle):
        return 0.85 + similarity * 0.09
    if needle in name:
        return 0.65 + similarity * 0.14
    return similarity * 0.8
