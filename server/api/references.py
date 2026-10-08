"""Independent food correspondences from CIQUAL, Agribalyse and Open Food Facts."""

from typing import Optional
from functools import lru_cache
from difflib import get_close_matches, SequenceMatcher
import asyncio
import re

from pydantic import BaseModel, Field

from api import agribalyse, off, ciqual, nutrition, nutrition_data, food_matching


class FoodReference(BaseModel):
    """Readable catalog food with its internal identifiers."""

    code: str
    name: str
    ciqual_code: Optional[str] = None
    missing_data: list[str] = Field(default_factory=list)
    no_data: bool = False
    automatic_match: bool | None = None
    label_ids: list[str] = Field(default_factory=list)
    origin_id: str | None = None


def product_label_ids(product: dict) -> list[str]:
    """Read declared taxonomy IDs only; free-text claims never imply certification."""
    tags = product.get("labels_tags")
    if not isinstance(tags, list):
        return []
    return list(dict.fromkeys(tag for tag in tags if isinstance(tag, str) and ":" in tag))


def product_origin_id(product: dict) -> str | None:
    """Accept one declared ingredient origin, never sales or manufacturing locations.

    Mixed, malformed and absent origins cannot populate the recipe's single origin cell.
    The caller resolves the ID against supported origins before using it for scoring.
    """
    tags = product.get("origins_tags")
    if not isinstance(tags, list) or not tags:
        return None
    if any(not isinstance(tag, str) or ":" not in tag for tag in tags):
        return None
    origins = set(tags)
    return next(iter(origins)) if len(origins) == 1 else None


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
        missing_data=["environmental_data"] if row.get("score") is None else [],
        no_data=row.get("score") is None,
        code=str(row["code"]),
        name=str(row.get("name_fr") or row.get("lci_name") or row["code"]),
        ciqual_code=str(row["ciqual_code"]) if row.get("ciqual_code") else None,
    )


def _normalize(text: str) -> str:
    """Ignore accents and case when searching catalog food names."""
    return ciqual.normalize(text)


def search_foods(
    query: str, limit: int, ciqual_only: bool = False, lang: str = "en", *, automatic: bool = False
) -> FoodReferencesResponse:
    """Search the selected database's own food identities."""
    if ciqual_only:
        return FoodReferencesResponse(
            foods=[_ciqual_reference(food, lang) for food in ciqual.search_foods(query, limit)]
        )
    needle = food_matching.recipe_name(query)
    if not needle:
        return FoodReferencesResponse(foods=[])
    matches = []
    for row in agribalyse.get_reference_rows():
        if row.get("score") is None:
            continue
        names = [_normalize(str(row.get(key) or "")) for key in ("name_fr", "lci_name")]
        rank = max(
            food_matching.automatic_rank(query, name)
            if automatic
            else ciqual._match_rank(needle, name)
            for name in names
        )
        if rank >= 0.45:
            matches.append((rank, _reference(row)))
    matches.sort(key=lambda item: (-item[0], item[1].name))
    return FoodReferencesResponse(foods=[reference for _, reference in matches[:limit]])


def _ciqual_reference(food: dict[str, str], lang: str) -> FoodReference:
    """Return an official CIQUAL food identity, independently of its environmental row."""
    composition = nutrition_data.get_foods().get(food["code"])
    values = nutrition._ciqual_values(composition)[0] if composition else {}
    return FoodReference(
        code=food["code"],
        ciqual_code=food["code"],
        name=ciqual.food_name(food, lang),
        missing_data=[key for key in nutrition.REQUIRED if values.get(key) is None],
        no_data=all(values.get(key) is None for key in nutrition.REQUIRED),
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
    # Nutrition references exist independently of Agribalyse coverage. In
    # particular fresh cream has a valid CIQUAL code but no environmental row;
    # fuzzy searching its label would incorrectly suggest fresh cream cheese.
    food = None
    if node:
        for member in off._node_chain(node):
            for prop in ("ciqual_food_code", "ciqual_proxy_food_code"):
                code = off._property_value(member, prop)
                if code and code in ciqual.get_foods():
                    food = ciqual.get_foods()[code]
                    break
            if food:
                break
    if food is None and environmental and environmental.ciqual_code:
        food = ciqual.get_foods().get(environmental.ciqual_code)
    if food is None and node:
        # Taxonomy codes can refer to retired entries. Search the current catalog instead.
        label = node.names.get(lang, node.names.get("en", node.names.get("fr", "")))
        candidates = ciqual.search_foods(_ingredient_search_term(label, lang), 1)
        food = candidates[0] if candidates else None
    nutrition = _ciqual_reference(food, lang) if food else None
    return IngredientReferencesResponse(agribalyse=environmental, ciqual=nutrition, source=source)


async def name_references(query: str, lang: str) -> IngredientReferencesResponse:
    """Keep exact taxonomy names and synonyms ahead of approximate catalog matches."""
    taxonomy = await off.get_ingredients_taxonomy()
    identifier = _taxonomy_identifier(taxonomy, query, lang)
    if not identifier:
        return IngredientReferencesResponse()
    return await ingredient_references(identifier, lang)


@lru_cache(maxsize=8)
def _taxonomy_names(taxonomy, lang: str) -> dict[str, str]:
    """Index each loaded taxonomy once, preferring canonical names over synonyms."""
    matches = {}
    for identifier, label, synonyms, _ in off.taxonomy_lang_label_and_synonyms(
        lang, taxonomy.iter_nodes()
    ):
        for rank, name in [(0, label), *((1, synonym) for synonym in synonyms)]:
            key = _normalize(name)
            matches[key] = min(matches.get(key, (rank, identifier)), (rank, identifier))
    return {name: match[1] for name, match in matches.items()}


def _taxonomy_identifier(taxonomy, query: str, lang: str) -> str | None:
    """Accept exact names or an unambiguous small typo in a multiword taxonomy name."""
    names = _taxonomy_names(taxonomy, lang)
    normalized = _normalize(query)
    if normalized in names:
        return names[normalized]
    terms = normalized.split()
    if len(terms) < 2:
        return None
    candidates = get_close_matches(normalized, names, n=3, cutoff=0.88)
    identifiers = {
        names[name]
        for name in candidates
        if len(name.split()) == len(terms)
        and all(SequenceMatcher(None, a, b).ratio() >= 0.8 for a, b in zip(terms, name.split()))
    }
    return next(iter(identifiers)) if len(identifiers) == 1 else None


async def product_aliases(query: str, lang: str, generic: list[dict]) -> list[str]:
    """Use catalog translations and exact taxonomy synonyms, never invented food aliases."""
    aliases = [query, product_search_term(query)]
    for food in generic:
        aliases.extend(food[key] for key in ("name_fr", "name_en") if food.get(key))
    # Taxonomy translations cover culinary names absent from the catalog, such as
    # a local name for a dough. Keep this optional dependency bounded.
    if not generic and not re.search(r'[:"]|\b(?:AND|OR|NOT)\b', query):
        try:
            taxonomy = await asyncio.wait_for(off.get_ingredients_taxonomy(), 1)
            identifier = _taxonomy_identifier(taxonomy, query, lang)
            if identifier:
                node = taxonomy[identifier]
                for language in (lang, "en", "fr"):
                    if node.names.get(language):
                        aliases.append(node.names[language])
                    aliases.extend(node.synonyms.get(language, []))
        except (OSError, ValueError, TimeoutError):
            pass
    return list(dict.fromkeys(aliases))


def product_match_name(query: str, name: str, values: dict) -> str:
    """Use declared fat composition when the catalog percentage is absent from packaging names.

    Only explicit fat-percentage requests use this evidence; cocoa percentages,
    product sizes and percentages already present in the name are not rewritten.
    """
    fat_request = re.search(r"%\s*(?:mg\b|fat\b|mat(?:iere|ière)?\b)", query, re.I)
    if not fat_request or re.search(r"\d+(?:[.,]\d+)?\s*%", name):
        return name
    fat = values.get("fat")
    if fat is None:
        return name
    return f"{name}, {fat:g}%"


async def product_references(
    query: str,
    lang: str,
    limit: int,
    *,
    _retry: bool = True,
    _search_query: str | None = None,
    _aliases: list[str] | None = None,
) -> FoodReferencesResponse:
    """Keep OFF relevance order and present identified products by name and brand."""
    if not query.strip():
        return FoodReferencesResponse(foods=[])
    generic = await asyncio.to_thread(ciqual.search_foods, query, 1, automatic=True)
    aliases = _aliases if _aliases is not None else await product_aliases(query, lang, generic)
    products = await off.search_products(_search_query or query.strip(), lang, limit)
    retried = False
    if not products and _retry:
        fallback = next((alias for alias in aliases if alias.strip() != query.strip()), "")
        if fallback:
            retried = True
            products = await off.search_products(fallback, lang, limit)
    foods = []
    composition = nutrition_data.get_foods().get(generic[0]["code"], {}) if generic else {}
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
        values, _ = nutrition._product_values(product, prepared=False)
        # Catalog suffixes contain bookkeeping and alternative preparations that
        # commercial labels do not repeat. Compare primary identities as well.
        automatic = bool(
            not food_matching.composition_conflict(query, name)
            and any(
                food_matching.automatic_rank(alias, product_match_name(alias, name, values))
                for alias in aliases
            )
        )
        categories = set(product.get("categories_tags") or [])
        # A product can share the ingredient name but belong to a different food family.
        # This catches chocolate truffles even when the product name just says 'Truffes'.
        if composition.get("group") == "02" and categories & {
            "en:chocolates",
            "en:chocolate-truffles",
            "en:confectioneries",
            "en:desserts",
            "en:dairies",
            "en:meats-and-their-products",
            "en:seafood",
        }:
            automatic = False
        foods.append(
            FoodReference(
                code=code,
                name=label,
                missing_data=[key for key in nutrition.REQUIRED if values.get(key) is None],
                no_data=all(values.get(key) is None for key in nutrition.REQUIRED),
                automatic_match=automatic,
                label_ids=product_label_ids(product),
                origin_id=product_origin_id(product),
            )
        )
    if _retry and not retried and foods and not any(food.automatic_match for food in foods):
        terms = {
            product_search_term(alias.split(",")[0])
            for alias in aliases
            if not re.search(r'[:"]|\b(?:AND|OR|NOT)\b', alias)
        }
        alternatives = [term for term in terms if _normalize(term) != _normalize(query)]
        fallback = min(alternatives, key=lambda term: (len(term), term)) if alternatives else query
        # Percent signs and catalog unit abbreviations are noisy search terms.
        # Keep the localized food and number; eligibility still checks the full variant.
        primary = product_search_term(query.split(",")[0])
        concise = re.sub(r"%\s*(?:mg\b|fat\b)", "", primary, flags=re.I).strip()
        if concise != primary:
            fallback = concise
        # Search a larger candidate pool only after the first page had no suitable
        # product. This also handles ambiguous names dominated by unrelated hits.
        try:
            retry = await product_references(
                query,
                lang,
                max(40, limit),
                _retry=False,
                _search_query=fallback,
                _aliases=aliases,
            )
        except (OSError, ValueError, TimeoutError):
            retry = FoodReferencesResponse(foods=[])
        if any(food.automatic_match for food in retry.foods):
            return FoodReferencesResponse(foods=retry.foods[:limit])
    foods.sort(key=lambda food: (not food.automatic_match, food.no_data, len(food.missing_data)))
    return FoodReferencesResponse(foods=foods[:limit])


def product_search_term(query: str) -> str:
    """Remove catalog bookkeeping for one fallback, keeping the leading food variant.

    Official generic food labels are not commercial product names. Their comma
    suffixes often describe uncertainty or averages. Do not broaden explicit
    search expressions or reduce the query to an arbitrary first word.
    """
    if re.search(r'[:"]|\b(?:AND|OR|NOT)\b', query):
        return query.strip()
    parts = query.split(",")
    head = parts[0].strip()
    head = re.sub(r"\((?:aliment moyen|average|moyenne)\)", "", head, flags=re.I)
    # Generic catalog disjunctions repeat the food after 'made from / à base de'.
    head = re.sub(
        r"^.+?\s+(?:ou (?:spécialité|préparation|produit) à base de|or (?:speciality|preparation|product) (?:made from|based on))\s+",
        "",
        head,
        flags=re.I,
    )
    # Catalog disjunctions describe a family rather than words that must all
    # occur on packaging. Keep its primary name and first explicit light variant.
    alternatives = re.split(r"\s+(?:ou|or)\s+", head, maxsplit=1, flags=re.I)
    if len(alternatives) == 2:
        variants = [
            word
            for word in re.findall(r"[^\W\d_]+", alternatives[1])
            if food_matching.normalize(word)
            in {"light", "reduced", "leger", "legere", "allege", "allegee", "reduit", "reduite"}
        ]
        head = " ".join([alternatives[0], *variants[:1]])
    # Preserve concise preparation, fat and salt descriptors. Uncertainty and
    # lists of possible variants are catalog metadata rather than product terms.
    qualifiers = []
    for part in parts[1:]:
        part = re.sub(r"\((?:aliment moyen|average|moyenne)\)", "", part, flags=re.I).strip()
        if not part or re.search(
            r"\b(?:sans précision|sans indication|without specification|unspecified|ou|or)\b",
            part,
            re.I,
        ):
            continue
        if len(part.split()) <= 4:
            qualifiers.append(part)
    return " ".join(" ".join([head, *qualifiers]).split())


def _local_references(
    lang: str = "en",
    query: str = "",
    ciqual_code: str | None = None,
    agribalyse_code: str | None = None,
) -> IngredientReferencesResponse:
    """Resolve each missing reference from linked codes and conservative local name search.

    An explicit code remains authoritative, including when unknown. Names without
    taxonomy IDs still receive the catalog's best available correspondence.
    """
    try:
        rows = agribalyse.get_reference_rows()
    except (OSError, ValueError):
        # Environmental catalog availability must not prevent CIQUAL resolution.
        rows = []
    environmental = (
        next((row for row in rows if str(row["code"]) == agribalyse_code), None)
        if agribalyse_code
        else None
    )
    food = ciqual.get_foods().get(ciqual_code) if ciqual_code else None
    if not ciqual_code and environmental:
        food = ciqual.get_foods().get(str(environmental.get("ciqual_code")))
    if food and not agribalyse_code:
        linked = [
            row
            for row in rows
            if str(row.get("ciqual_code")) == food["code"] and row.get("score") is not None
        ]
        if len(linked) == 1:
            environmental = linked[0]
    result = IngredientReferencesResponse(
        ciqual=_ciqual_reference(food, lang) if food else None,
        agribalyse=_reference(environmental) if environmental else None,
        source="catalog" if environmental else None,
    )
    if not result.ciqual and not ciqual_code and query.strip():
        matches = ciqual.search_foods(query.strip(), 1, automatic=True)
        if matches:
            result.ciqual = _ciqual_reference(matches[0], lang)
    if not result.agribalyse and not agribalyse_code:
        linked = sorted(
            (
                row
                for row in rows
                if result.ciqual
                and str(row.get("ciqual_code")) == result.ciqual.code
                and row.get("score") is not None
            ),
            key=lambda row: str(row["code"]),
        )
        if linked:
            result.agribalyse = _reference(linked[0])
            result.source = "ciqual_code"
        elif query.strip() and rows:
            # Prefer the resolved food's preparation/variant before the original short name.
            food = ciqual.get_foods().get(result.ciqual.code) if result.ciqual else None
            preferred = ciqual.food_name(food, "fr") if food else query.strip()
            preferred = re.sub(r"\s*\((?:aliment moyen|average)\)", "", preferred, flags=re.I)
            queries = dict.fromkeys([preferred, product_search_term(preferred), query.strip()])
            for term in queries:
                matches = search_foods(term, 8, automatic=True).foods
                if food:
                    matches = [
                        match
                        for match in matches
                        if food_matching.automatic_rank(preferred, match.name)
                    ]
                if matches:
                    result.agribalyse = matches[0]
                    result.source = "name_match"
                    break
    if not result.agribalyse:
        result.source = "unmatched"
    return result


async def resolve_ingredient_references(
    taxonomy_id: str | None = None,
    lang: str = "en",
    query: str = "",
    ciqual_code: str | None = None,
    agribalyse_code: str | None = None,
) -> IngredientReferencesResponse:
    """Prefer precise local identities over broad taxonomy proxies, without waiting on OFF.

    Taxonomy synonyms remain a bounded fallback for names absent from the local
    catalogues. Explicit selections remain authoritative, even if their codes are unknown.
    """
    result = await asyncio.to_thread(_local_references, lang, query, ciqual_code, agribalyse_code)
    if (result.ciqual and (query.strip() or result.agribalyse)) or (
        ciqual_code and agribalyse_code
    ):
        return result
    if not taxonomy_id and not query.strip():
        return result
    try:
        mapped = await asyncio.wait_for(
            ingredient_references(taxonomy_id, lang)
            if taxonomy_id
            else name_references(query.strip(), lang),
            1,
        )
    except (OSError, ValueError, TimeoutError):
        return result
    if not result.ciqual and not ciqual_code:
        result.ciqual = mapped.ciqual
        if result.ciqual and not result.agribalyse and not agribalyse_code:
            linked = await asyncio.to_thread(
                _local_references, lang, query, result.ciqual.code, None
            )
            result.agribalyse = linked.agribalyse
            result.source = linked.source
    if (
        not result.agribalyse
        and not agribalyse_code
        and mapped.agribalyse
        and (not query.strip() or food_matching.automatic_rank(query, mapped.agribalyse.name))
    ):
        result.agribalyse = mapped.agribalyse
        result.source = mapped.source
    return result
