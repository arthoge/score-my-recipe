"""Calls to openfoodfacts API"""

from typing import Iterable, Optional
import asyncio

from async_lru import alru_cache as async_cache
import openfoodfacts
import openfoodfacts.taxonomy as taxonomy

from api.types import OFFIngredient
from api.settings import OpenFoodFactsEnvironments, get_settings

USER_AGENT = "Score-my-recipe - openfoodfacts"


def off_env_setting(off_env: OpenFoodFactsEnvironments) -> openfoodfacts.Environment:
    """Get the corresponding openfoodfacts.Environment for the given OpenFoodFactsEnvironments enum value."""
    if off_env == OpenFoodFactsEnvironments.STAGING:
        return openfoodfacts.Environment.net
    else:
        return openfoodfacts.Environment.org


off_api = openfoodfacts.API(
    user_agent=USER_AGENT,
    version="v3",
    environment=off_env_setting(get_settings().openfoodfacts_env),
)


async def parse_text(text: str, lang: str) -> list[OFFIngredient]:
    """Parse a text and return a list of ingredients"""
    # TODO: handle RuntimeError case
    # useful example if you want to test the parsing API with curl:
    # ```bash
    # curl -X PATCH "https://world.openfoodfacts.net/api/v3/product/test" \
    #     -H "User-Agent: test parsing" \
    #     --cookie "session=" \
    #     -H "Content-Type: application/json" \
    #     -d '{
    #         "lc": "fr",
    #         "cc": "fr",
    #         "fields": "ingredients",
    #         "product": {
    #         "ingredients_text_fr": "2 œuf, 2kg de patates bio et vegan de france, 300ml de lait, 20g de tomate concentrée, persil"
    #         }
    #     }'
    # ```
    # TODO: change openfoodfacts package to be able to use async ?
    ingredients_data = await asyncio.to_thread(off_api.product.parse_ingredients, text, lang)
    return [OFFIngredient(**ingredient) for ingredient in ingredients_data]


# type helper, we first have the id, then the label, then the synonyms,
# then any additional properties
TaxonomyLangLabelType = list[tuple[str, str, list[str], list[Optional[str]]]]


def taxonomy_lang_label_and_synonyms(
    lang: str,
    entries: Iterable[taxonomy.TaxonomyNode],
    *properties: str,
) -> TaxonomyLangLabelType:
    """Get the list of (id, label, synonyms) for a given language from a list of
    taxonomy entries.

    Both label and synonyms fall back to the "xx" (neutral) language then to
    english if they are not available in the requested language.
    """
    result: TaxonomyLangLabelType = []
    for entry in entries:
        label = entry.names.get(lang, entry.names.get("xx", entry.names.get("en", entry.id)))
        synonyms = entry.synonyms.get(lang, entry.synonyms.get("xx", entry.synonyms.get("en", [])))
        property_values = [_property_value(entry, prop) for prop in properties]
        data = (entry.id, label, synonyms, property_values)
        result.append(data)
    return result


@async_cache(maxsize=1)
async def get_origins_taxonomy() -> taxonomy.Taxonomy:
    """Get the origins taxonomy from Open Food Facts API"""
    origins_taxonomy = await asyncio.to_thread(
        taxonomy.get_taxonomy,
        taxonomy.TaxonomyType.origin,
        cache_dir=get_settings().cache_dir,
    )
    return origins_taxonomy


@async_cache(maxsize=1)
async def get_ingredients_taxonomy() -> taxonomy.Taxonomy:
    """Get the ingredients taxonomy from Open Food Facts API"""
    ingredients_taxonomy = await asyncio.to_thread(
        taxonomy.get_taxonomy,
        taxonomy.TaxonomyType.ingredient,
        cache_dir=get_settings().cache_dir,
    )
    return ingredients_taxonomy


@async_cache(maxsize=1)
async def get_units_taxonomy() -> taxonomy.Taxonomy:
    """Get the units taxonomy from Open Food Facts API.

    The units taxonomy is not (yet) exposed as a ``TaxonomyType`` by the
    openfoodfacts SDK, so we download and cache it manually, reusing the same
    download/cache helpers as :func:`taxonomy.get_taxonomy`.
    """
    from openfoodfacts import Flavor
    from openfoodfacts.utils import URLBuilder, download_file, should_download_file

    environment = off_env_setting(get_settings().openfoodfacts_env)
    url = f"{URLBuilder.static(Flavor.off, environment)}/data/taxonomies/units.full.json"
    cache_dir = get_settings().cache_dir
    taxonomy_path = cache_dir / "off-unit.json"

    def _load_or_download() -> taxonomy.Taxonomy:
        # Reuse the SDK caching logic: only (re)download when the cached file
        # is missing (we keep download_newer=False for parity with the other
        # taxonomy fetchers and to avoid a HEAD request on every call).
        if not should_download_file(url, taxonomy_path, force_download=False, download_newer=False):
            return taxonomy.Taxonomy.from_path(taxonomy_path)
        cache_dir.mkdir(parents=True, exist_ok=True)
        download_file(url, taxonomy_path)
        return taxonomy.Taxonomy.from_path(taxonomy_path)

    return await asyncio.to_thread(_load_or_download)


@async_cache(maxsize=1)
async def get_labels_taxonomy() -> taxonomy.Taxonomy:
    """Get the labels taxonomy from Open Food Facts API"""
    labels_taxonomy = await asyncio.to_thread(
        taxonomy.get_taxonomy,
        taxonomy.TaxonomyType.label,
        cache_dir=get_settings().cache_dir,
    )
    return labels_taxonomy


async def get_countries_taxonomy() -> taxonomy.Taxonomy:
    """Get the countries taxonomy from Open Food Facts API"""
    countries_taxonomy = await asyncio.to_thread(
        taxonomy.get_taxonomy, taxonomy.TaxonomyType.country, cache_dir=get_settings().cache_dir
    )
    return countries_taxonomy


async def get_languages_taxonomy() -> taxonomy.Taxonomy:
    """Get the languages taxonomy from Open Food Facts API"""
    languages_taxonomy = await asyncio.to_thread(
        taxonomy.get_taxonomy, taxonomy.TaxonomyType.language, cache_dir=get_settings().cache_dir
    )
    return languages_taxonomy


def _node_chain(node: taxonomy.TaxonomyNode) -> list[taxonomy.TaxonomyNode]:
    """Return the node followed by all its parents (closest first)."""
    return [node, *node.get_parents_hierarchy()]


def _property_value(node: taxonomy.TaxonomyNode, prop: str) -> Optional[str]:
    """Read a code property from a taxonomy node.

    Taxonomy properties are stored as language -> value dicts (e.g.
    `{"en": "25525"}`); we return the value, preferring English then any.
    """
    raw = node.properties.get(prop)
    if raw is None:
        return None
    if isinstance(raw, dict):
        value = raw.get("en") or next(iter(raw.values()), None)
        return str(value) if value is not None else None
    return str(raw)


@async_cache(maxsize=1)
async def origins_by_country_code() -> dict[str, str]:
    """Get a dict mapping 2-letter country codes to the corresponding origin id

    We also add children
    """
    origins_taxonomy = await get_origins_taxonomy()
    values = [
        (origin, _property_value(origin, "country_code_2"))
        for origin in origins_taxonomy.iter_nodes()
    ]
    country_to_origins = {
        country_code.upper(): origin for origin, country_code in values if country_code
    }
    return {country_code: origin.id for country_code, origin in country_to_origins.items()}


@async_cache(maxsize=1)
async def origin_to_country_origin() -> dict[str, str]:
    """Get a dict mapping origin id to the corresponding country origin id"""
    country_origins = await origins_by_country_code()
    result = {origin_id: origin_id for origin_id in country_origins.values()}
    # add children
    origins_taxonomy = await get_origins_taxonomy()
    for origin_id in list(result.keys()):
        try:
            origin_node = origins_taxonomy[origin_id]
        except KeyError:
            continue
        for child in origin_node.get_children_hierarchy():
            result[child.id] = origin_id
    return result


@async_cache(maxsize=1)
async def languages_by_code() -> dict[str, str]:
    languages_taxonomy = await get_languages_taxonomy()
    _iter = (
        (_property_value(node, "language_code_2"), node.id)
        for node in languages_taxonomy.iter_nodes()
    )
    return {code: node_id for code, node_id in _iter if code is not None}
