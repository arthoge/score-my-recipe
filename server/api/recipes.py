"""This is the programmatic API for recipes scoring.

Contains the recipe-level business logic: ingredient parsing and the
origins/labels/countries/ingredients taxonomies.
"""

import logging
import re

from async_lru import alru_cache as async_lru_cache

import api.agribalyse as agribalyse
import api.off as off
import api.types as types
import api.score_data as score_data
from api.lang import two_letter_lang_code

logger = logging.getLogger(__name__)


# A numeric value (with an eventual dot) and a unit
QUANTITY_UNIT_REGEX = re.compile(r"^\s*(?P<value>\d+(\.\d+)?)\s*(?P<unit>\w+)?\s*$")


def off_ingredient_to_recipe_ingredient(
    off_ingredient: types.OFFIngredient,
) -> types.RecipeIngredient:
    """Convert an OFFIngredient to a RecipeIngredient"""
    # handle original quantity and unit
    quantity_value = None
    quantity_unit = None
    if off_ingredient.quantity is not None:
        # get quantity / unit
        matched = QUANTITY_UNIT_REGEX.match(off_ingredient.quantity)
        if matched:
            if matched.group("value"):
                quantity_value = float(matched.group("value"))
            if matched.group("unit"):
                quantity_unit = matched.group("unit")
    ingredient = types.RecipeIngredient(
        taxonomy_id=off_ingredient.id,
        codified_ingredient=off_ingredient.text,
        is_in_taxonomy=bool(off_ingredient.is_in_taxonomy),
        quantity_g=off_ingredient.quantity_g,
        quantity_value=quantity_value,
        quantity_unit=quantity_unit,
    )
    return ingredient


async def parse_text(text: str, lang: str) -> list[types.RecipeIngredient]:
    """Parse a text and return a list of ingredients with quantities and eventual modifiers"""
    # normalize the language code (eg. "fr-FR" or "fr_FR" to "fr"), as the OFF
    # ingredient parsing API only accepts 2-letter language codes
    lang = two_letter_lang_code(lang)
    off_ingredients = await off.parse_text(text, lang)
    ingredients = [
        off_ingredient_to_recipe_ingredient(ingredient) for ingredient in off_ingredients
    ]
    return ingredients


@async_lru_cache(maxsize=200)
async def _get_origins_entries(lang: str) -> off.TaxonomyLangLabelType:
    """Internal version of get_origins that caches the result for a given language code"""
    origins_taxonomy = await off.get_origins_taxonomy()
    # only keep origins that have bonus/malus
    epi_modifiers = await score_data.get_epi_modifiers()
    origins = {origin for origin in origins_taxonomy.iter_nodes() if origin.id in epi_modifiers}
    # add children
    for origin in list(origins):
        origins.update(origin.get_children_hierarchy())
    # verify all origins are included
    missing_origins = set(epi_modifiers.keys()) - {origin.id for origin in origins}
    if missing_origins:
        # log a warning
        logger.warning(f"Missing origins in taxonomy: {missing_origins}")
    # sort by id for predictable order
    origins_list = off.taxonomy_lang_label_and_synonyms(lang, origins)
    origins_list.sort(key=lambda x: x[0])
    return origins_list


async def get_origins(lang: str, include_synonyms: bool = False) -> list[types.Origin]:
    """Get the list of origins available in the database

    Note: as the list is not too big, we let clients handle suggestions to users
    """
    lang = two_letter_lang_code(lang)
    origins = await _get_origins_entries(lang)
    return [
        types.Origin(
            id=origin_id, label=origin_label, synonyms=origin_synonyms if include_synonyms else None
        )
        for origin_id, origin_label, origin_synonyms, _ in origins
    ]


ALL_GREEN_SCORE_LABELS = set(label for label in score_data.LABELS_BONUS.keys())


@async_lru_cache(maxsize=200)
async def _get_labels_entries(lang: str) -> off.TaxonomyLangLabelType:
    """Internal version of get_labels that caches the result for a given language code"""
    labels_taxonomy = await off.get_labels_taxonomy()
    all_labels = labels_taxonomy.iter_nodes()
    filtered_labels = {label for label in all_labels if label.id in ALL_GREEN_SCORE_LABELS}
    # add children of relevant labels
    for label in list(filtered_labels):
        filtered_labels.update(label.get_children_hierarchy())
    # verify all green score labels are included
    missing_labels = ALL_GREEN_SCORE_LABELS - {label.id for label in filtered_labels}
    if missing_labels:
        # log a warning
        logger.warning(f"Missing green-score relevant labels in taxonomy: {missing_labels}")
    labels_list = off.taxonomy_lang_label_and_synonyms(lang, filtered_labels)
    # sort by id for predictable order
    labels_list.sort(key=lambda x: x[0])
    return labels_list


async def get_labels(lang: str, include_synonyms: bool = False) -> list[types.Label]:
    """Get the list of labels relevant for green-score computation

    The list is filtered to only include labels that impact the green-score
    """
    lang = two_letter_lang_code(lang)
    _labels = await _get_labels_entries(lang)
    return [
        types.Label(
            id=label_id, label=label_label, synonyms=label_synonyms if include_synonyms else None
        )
        for label_id, label_label, label_synonyms, _ in _labels
    ]


@async_lru_cache(maxsize=200)
async def get_countries_entries(lang: str) -> off.TaxonomyLangLabelType:
    """Internal version of get_countries that caches the result for a given language code"""
    countries_taxonomy = await off.get_countries_taxonomy()
    all_countries = countries_taxonomy.iter_nodes()
    origins_by_country_code = await off.origins_by_country_code()
    country_ids = set(origins_by_country_code.values())
    filtered_countries = {country for country in all_countries if country.id in country_ids}
    # verify all green score countries are included
    missing_countries = country_ids - {country.id for country in filtered_countries}
    if missing_countries:
        # log a warning
        logger.warning(f"Missing green-score relevant countries in taxonomy: {missing_countries}")
    countries_list = off.taxonomy_lang_label_and_synonyms(
        lang, filtered_countries, "country_code_2"
    )
    # sort by id for predictable order
    countries_list.sort(key=lambda x: x[0])
    return countries_list


async def get_countries(lang: str, include_synonyms: bool = False) -> list[types.Country]:
    """Get the list of countries relevant for green-score computation

    The list is filtered to only include labels that impact the green-score
    """
    lang = two_letter_lang_code(lang)
    _countries = await get_countries_entries(lang)
    return [
        types.Country(
            id=country_id,
            label=country_label,
            synonyms=country_synonyms if include_synonyms else None,
            country_code=country_code_2.upper() if country_code_2 else None,
        )
        for country_id, country_label, country_synonyms, (country_code_2,) in _countries
    ]


@async_lru_cache(maxsize=200)
async def _get_ingredients_entries(lang: str) -> off.TaxonomyLangLabelType:
    """Internal version of get_ingredients that caches the result for a given language code"""
    ingredients_taxonomy = await off.get_ingredients_taxonomy()
    ingredients_list = off.taxonomy_lang_label_and_synonyms(lang, ingredients_taxonomy.iter_nodes())
    # sort by id for predictable order
    ingredients_list.sort(key=lambda x: x[0])
    return ingredients_list


async def get_ingredients(lang: str, include_synonyms: bool = False) -> list[types.Ingredient]:
    """Get the list of ingredients relevant for green-score computation"""
    lang = two_letter_lang_code(lang)
    _ingredients = await _get_ingredients_entries(lang)
    return [
        types.Ingredient(
            id=ingredient_id,
            label=ingredient_label,
            synonyms=ingredient_synonyms if include_synonyms else None,
        )
        for ingredient_id, ingredient_label, ingredient_synonyms, _ in _ingredients
    ]


async def suggest_scored_ingredient(
    lang: str, include_synonyms: bool, taxonomy_id: str
) -> list[types.ScoredIngredient]:
    """Suggest scored ingredient alternatives for a taxonomy id.

    Walks down the ingredients taxonomy from the node matching ``taxonomy_id``
    and returns the nodes that resolve to an Agribalyse row, as a list of
    ingredients (same structure as :func:`get_ingredients`) each annotated with
    its Agribalyse row code.

    Returns an empty list when the taxonomy id is unknown or no descendant
    resolves to an Agribalyse row.
    """
    lang = two_letter_lang_code(lang)
    ingredients_taxonomy = await off.get_ingredients_taxonomy()
    node = ingredients_taxonomy[taxonomy_id] if taxonomy_id in ingredients_taxonomy else None
    if node is None:
        return []

    suggestions = agribalyse.suggest_scored_ingredient(node)
    if not suggestions:
        return []

    # Resolve localized labels/synonyms for the matched nodes in one pass.
    labels = off.taxonomy_lang_label_and_synonyms(lang, [n for n, _ in suggestions])
    code_by_id = {n.id: code for n, code in suggestions}
    return [
        types.ScoredIngredient(
            id=ingredient_id,
            label=ingredient_label,
            synonyms=ingredient_synonyms if include_synonyms else None,
            agribalyse_code=code_by_id[ingredient_id],
        )
        for ingredient_id, ingredient_label, ingredient_synonyms, _ in labels
    ]
