"""Versioned ANSES CIQUAL food identities, independent from environmental references."""

from functools import lru_cache
from pathlib import Path
from difflib import SequenceMatcher
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from api import food_matching

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
    return food_matching.normalize(text)


def search_foods(query: str, limit: int = 8, *, automatic: bool = False) -> list[dict[str, str]]:
    """Search both official languages, keeping distinct raw, cooked and drained foods."""
    needle = food_matching.recipe_name(query)
    if not needle:
        return []
    matches = []
    for food in get_foods().values():
        names = [normalize(food[key]) for key in ("name_fr", "name_en")]
        rank = max(
            food_matching.automatic_rank(query, name) if automatic else _match_rank(needle, name)
            for name in names
        )
        if rank >= 0.45:
            matches.append((rank, food))
    matches.sort(key=lambda item: (-item[0], item[1]["code"]))
    return [food for _, food in matches[:limit]]


def _match_rank(needle: str, name: str) -> float:
    """Prefer a food named by the query over composite dishes containing that ingredient."""
    automatic = food_matching.automatic_rank(needle, name)
    if automatic:
        return automatic
    return min(0.79, _manual_match_rank(needle, name))


def _manual_match_rank(needle: str, name: str) -> float:
    """Keep broad manual results below verified automatic correspondences."""
    if needle == name:
        return 1.0
    query_terms, target_terms = food_matching.words(needle), food_matching.words(name)
    if not query_terms or not target_terms:
        return 0.0
    # Discard unrelated catalogue entries before doing any full-string fuzzy comparison.
    if (
        query_terms[0] not in target_terms
        and SequenceMatcher(None, query_terms[0], target_terms[0]).ratio() < 0.8
    ):
        return 0.0
    # Simple English/French plurals should not promote a soup over the ingredient.
    needle, name = (
        re.sub(r"\b([a-z]{3,})s\b", lambda m: m[0] if m[0].endswith(("ss", "us")) else m[1], text)
        for text in (needle, name)
    )
    similarity = SequenceMatcher(None, needle, name).ratio()
    average = "(average)" in name or "(aliment moyen)" in name
    if name.startswith(needle + ","):
        raw = bool(re.search(r"\b(?:raw|cru|crue)\b", name))
        return 0.95 + similarity * 0.01 + (0.02 if average else 0) + (0.015 if raw else 0)
    if re.match(re.escape(needle) + r"(?:\b|$)", name):
        # A compound such as 'butter of cocoa' is less generic than a fat percentage.
        compound = bool(re.match(r"\s+(?:de\b|d'|of\b|with\b)", name[len(needle) :]))
        return 0.85 + similarity * 0.05 + (0.08 if average else 0) - (0.08 if compound else 0)
    if re.search(r"\b" + re.escape(needle) + r"\b", name):
        return 0.65 + similarity * 0.14
    query_words, name_words = (re.findall(r"[a-z]+", text) for text in (needle, name))
    # Approximation must preserve the food identity, not just a shared adjective.
    # Names with unrecognized qualifiers remain available through taxonomy synonyms.
    if not query_words or not name_words:
        return 0.0
    if SequenceMatcher(None, query_words[0], name_words[0]).ratio() < 0.8:
        return 0.0
    if set(query_words) <= set(name_words):
        return 0.8 + similarity * 0.05
    if any(
        len(word) > 3
        and not any(
            SequenceMatcher(None, word, candidate).ratio() >= 0.8 for candidate in name_words
        )
        for word in query_words[1:]
    ):
        return 0.0
    return similarity * 0.8
