"""Independent food correspondences from CIQUAL, Agribalyse and Open Food Facts."""

from difflib import SequenceMatcher
from typing import Optional
import unicodedata

from pydantic import BaseModel

from api import agribalyse, off, ciqual


class FoodReference(BaseModel):
    """Readable catalog food with its internal identifiers."""

    code: str
    name: str
    ciqual_code: Optional[str] = None


class FoodReferencesResponse(BaseModel):
    """Named search results from a food reference database."""

    foods: list[FoodReference]


class IngredientReferencesResponse(BaseModel):
    """Proposed correspondences from the taxonomy mapping, including proxy provenance."""

    agribalyse: Optional[FoodReference] = None
    ciqual: Optional[FoodReference] = None
    source: Optional[str] = None


def _reference(row: dict) -> FoodReference:
    """Keep catalog identifiers separate from food names displayed to the chef."""
    return FoodReference(
        code=str(row["code"]),
        name=str(row.get("name_fr") or row.get("lci_name") or row["code"]),
        ciqual_code=str(row["ciqual_code"]) if row.get("ciqual_code") else None,
    )


def _normalize(text: str) -> str:
    """Ignore accents and case when searching catalog food names."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower().strip())
        if not unicodedata.combining(char)
    )


def search_foods(
    query: str, limit: int, ciqual_only: bool = False, lang: str = "en"
) -> FoodReferencesResponse:
    """Search the selected database's own food identities."""
    if ciqual_only:
        return FoodReferencesResponse(
            foods=[_ciqual_reference(food, lang) for food in ciqual.search_foods(query, limit)]
        )
    needle = _normalize(query)
    if not needle:
        return FoodReferencesResponse(foods=[])
    matches = []
    for row in agribalyse.get_reference_rows():
        if row.get("score") is None:
            continue
        names = [_normalize(str(row.get(key) or "")) for key in ("name_fr", "lci_name")]
        rank = max(
            (
                1.0
                if needle == name
                else 0.9
                if needle in name
                else SequenceMatcher(None, needle, name).ratio()
            )
            for name in names
        )
        if rank >= 0.45:
            matches.append((rank, _reference(row)))
    matches.sort(key=lambda item: (-item[0], item[1].name))
    return FoodReferencesResponse(foods=[reference for _, reference in matches[:limit]])


def _ciqual_reference(food: dict[str, str], lang: str) -> FoodReference:
    """Return an official CIQUAL food identity, independently of its environmental row."""
    return FoodReference(
        code=food["code"], ciqual_code=food["code"], name=ciqual.food_name(food, lang)
    )


def _ingredient_search_term(label: str, lang: str) -> str:
    """Handle common English taxonomy plurals when the official food name is singular."""
    if lang.startswith("en"):
        if label.lower().endswith("oes"):
            return label[:-2]
        if label.lower().endswith("s") and not label.lower().endswith(("ss", "us")):
            return label[:-1]
    return label


async def ingredient_references(taxonomy_id: str, lang: str = "en") -> IngredientReferencesResponse:
    """Resolve each database independently, validating linked codes against the CIQUAL release."""
    taxonomy = await off.get_ingredients_taxonomy()
    node = taxonomy[taxonomy_id] if taxonomy_id in taxonomy else None
    _, source, row = agribalyse.find_agribalyse_row(node)
    environmental = _reference(row) if row else None
    food = (
        ciqual.get_foods().get(environmental.ciqual_code)
        if environmental and environmental.ciqual_code
        else None
    )
    if food is None and node:
        # Taxonomy codes can refer to retired entries. Search the current catalog instead.
        label = node.names.get(lang, node.names.get("en", node.names.get("fr", "")))
        candidates = ciqual.search_foods(_ingredient_search_term(label, lang), 1)
        food = candidates[0] if candidates else None
    nutrition = _ciqual_reference(food, lang) if food else None
    return IngredientReferencesResponse(agribalyse=environmental, ciqual=nutrition, source=source)


async def product_references(query: str, lang: str, limit: int) -> FoodReferencesResponse:
    """Keep OFF relevance order and present identified products by name and brand."""
    if not query.strip():
        return FoodReferencesResponse(foods=[])
    products = await off.search_products(query.strip(), lang, limit)
    foods = []
    for product in products:
        code = product.get("code")
        name = product.get(f"product_name_{lang}") or product.get("product_name")
        if isinstance(name, dict):
            name = name.get(lang) or name.get("en") or next(iter(name.values()), "")
        if (
            not isinstance(code, str)
            or not code.strip()
            or not isinstance(name, str)
            or not name.strip()
        ):
            continue
        brands = product.get("brands")
        if isinstance(brands, list):
            brands = ", ".join(brand for brand in brands if isinstance(brand, str))
        label = (
            f"{name.strip()} — {brands.strip()}"
            if isinstance(brands, str) and brands.strip()
            else name.strip()
        )
        foods.append(FoodReference(code=code, name=label))
    return FoodReferencesResponse(foods=foods[:limit])
