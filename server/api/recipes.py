"""This is the programmatic API for recipes scoring.
It contains all the business logic.
"""

import logging
import re
import unicodedata

from async_lru import alru_cache as async_lru_cache

import api.agribalyse as agribalyse
import api.exceptions as exceptions
import api.off as off
import api.types as types
import api.score_data as score_data

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


def two_letter_lang_code(lang: str) -> str:
    """Convert a language code to a 2-letter code"""
    return lang.replace("_", "-").split("-")[0]


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


# Standard units we expose to clients: only mass (g) and volume (ml) are
# relevant for recipe quantities, so units relying on other standard units
# (e.g. energy in kJ) are filtered out.
ALLOWED_STANDARD_UNITS = ("g", "ml")


@async_lru_cache(maxsize=200)
async def _get_units_entries(lang: str) -> off.TaxonomyLangLabelType:
    """Internal version of get_units that caches the result for a given language code"""
    units_taxonomy = await off.get_units_taxonomy()
    units_list = off.taxonomy_lang_label_and_synonyms(
        lang, units_taxonomy.iter_nodes(), "standard_unit"
    )
    # only keep units whose standard_unit is a mass (g) or volume (ml)
    units_list = [unit for unit in units_list if unit[3][0] in ALLOWED_STANDARD_UNITS]
    # sort by id for predictable order
    units_list.sort(key=lambda x: x[0])
    return units_list


async def get_units(lang: str, include_synonyms: bool = False) -> list[types.Unit]:
    """Get the list of units available in the Open Food Facts units taxonomy"""
    lang = two_letter_lang_code(lang)
    _units = await _get_units_entries(lang)
    return [
        types.Unit(
            id=unit_id,
            label=unit_label,
            synonyms=unit_synonyms if include_synonyms else None,
            standard_unit=standard_unit,
        )
        for unit_id, unit_label, unit_synonyms, (standard_unit,) in _units
    ]


def _normalize_unit_name(name: str) -> str:
    """Normalize a unit name for case- and accent-insensitive lookup.

    Lowercases, strips surrounding whitespace, removes accents (e.g. ``"pièce"``
    -> ``"piece"``) and replaces spaces with ``-`` (so ``"fl oz"`` matches the
    ``"fl-oz"`` form used in taxonomy slugs).
    """
    # decompose accents and drop the combining marks (NFKD + ASCII round-trip)
    no_accents = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return no_accents.strip().lower().replace(" ", "-")


@async_lru_cache(maxsize=200)
async def _unit_name_to_id(lang: str) -> dict[str, str]:
    """Cached mapping of normalized unit name -> taxonomy id, for ``lang`` and ``xx``.

    Built only from the units returned by :func:`_get_units_entries` (i.e. mass
    and volume units). Translations from both the requested ``lang`` (which
    already falls back to ``xx``/``en`` for missing entries) and the neutral
    ``xx`` language are merged, so language-neutral abbreviations such as
    ``"kg"`` (the ``xx`` name of ``xx:kg``) resolve regardless of the requested
    language.

    Both the canonical label and every synonym are used as keys. On a collision
    (a name shared by two units) the first-seen unit wins and a warning is logged.
    """
    name_to_id: dict[str, str] = {}
    # merge the requested language and the neutral "xx" language
    for entries in (await _get_units_entries(lang), await _get_units_entries("xx")):
        for unit_id, label, synonyms, _ in entries:
            for translation in (label, *(synonyms or [])):
                key = _normalize_unit_name(translation)
                if not key:
                    continue
                if key in name_to_id and name_to_id[key] != unit_id:
                    logger.warning(
                        "Unit name '%s' maps to both '%s' and '%s'; keeping '%s'.",
                        translation,
                        name_to_id[key],
                        unit_id,
                        name_to_id[key],
                    )
                else:
                    name_to_id[key] = unit_id
    return name_to_id


async def _resolve_unit_name(name: str, lang: str) -> str | None:
    """Resolve a localized unit name to its taxonomy id, or ``None`` if unknown.

    Probes the cached name->id mapping built from :func:`_get_units_entries` for
    ``lang`` (which already merges the neutral ``xx`` language, so abbreviations
    like ``"kg"`` resolve for any language).
    """
    name_to_id = await _unit_name_to_id(lang)
    return name_to_id.get(_normalize_unit_name(name))


async def recompute_quantity(
    quantity_g: float,
    old_value: float,
    old_unit: str,
    new_value: float,
    new_unit: str,
    lang: str,
) -> tuple[float, float, str]:
    """Recompute the quantity in grams after the user edited an ingredient's value/unit.

    Given the previous ``(value, unit, grams)`` and the new ``(value, unit)``,
    returns ``(new_quantity_g, new_value, new_unit)``.

    Units may be given either as a taxonomy id (e.g. ``xx:kg``), as a localized
    unit name (e.g. ``"kg"``) resolved through ``lang`` (and the neutral ``xx``
    language), or as the ``{types.ITEM_UNIT}`` sentinel for countable ingredients.
    The ``new_unit`` is only resolved when its conversion factor is actually
    needed (the unit cancels out in a plain cross-multiplication); ``old_unit``
    is only resolved when the units differ but share the same standard unit (so
    the grams can be cross-multiplied through it), otherwise it is only compared
    as-is to detect an unchanged unit.

    We do our best to recompute it in a simple manner,
    but some unit conversions will require calling the Open Food Facts parse API
    (not yet implemented).
    """
    lang = two_letter_lang_code(lang)
    # Case 1: the unit did not change -> cross-multiplication (the unit cancels out).
    if new_unit == old_unit:
        if old_value != 0:
            return quantity_g * (new_value / old_value), new_value, new_unit
        # A zero old value cannot be cross-multiplied. Fall back to the mass
        # conversion factor of the (unchanged) unit when it is a mass unit, so
        # that e.g. editing "0 kg" -> "2 kg" still yields 2000 g.
        # TODO: for non-mass units, call the Open Food Facts parse API to
        # recover the quantity in grams.
        new_quantity_g = await _quantity_from_mass_unit(new_value, new_unit, lang)
        if new_quantity_g is not None:
            return new_quantity_g, new_value, new_unit
        raise exceptions.UnitConversionNotSupportedError(
            f"Cannot recompute the quantity from a zero old value with unit '{new_unit}'."
        )

    # The unit changed: we need the new unit's conversion info from the taxonomy.
    # ``types.ITEM_UNIT`` is a countable sentinel with no conversion factor.
    if new_unit == types.ITEM_UNIT:
        # TODO: call the Open Food Facts parse API to convert to a countable unit.
        raise exceptions.UnitConversionNotSupportedError(
            f"Converting to the countable unit '{types.ITEM_UNIT}' is not supported yet."
        )

    # Resolve the new unit's standard_unit and conversion factor up front (needed for case 2 and case 3)
    # Raises UnknownUnitError if the new unit is not a resolvable name.
    new_standard_unit, new_factor = await _unit_conversion(new_unit, lang)

    # Case 2: the old and new units share the same standard_unit (e.g. both are
    # mass, or both are volume) and the previous value is non-zero. Because both
    # units live in the same dimension, the (unknown) density cancels out: the
    # grams scale in the same proportion as the conversion factors, so we can
    # cross-multiply through the standard unit.
    #   new_quantity_g = quantity_g * (new_value * new_factor) / (old_value * old_factor)
    # This is what makes e.g. "2 cups" -> "500 ml" computable without a density.
    if old_value != 0 and old_unit != types.ITEM_UNIT:
        old_standard_unit, old_factor = await _safe_unit_conversion(old_unit, lang)
        if (
            old_standard_unit is not None
            and old_standard_unit == new_standard_unit
            and old_factor is not None
            and new_factor is not None
        ):
            return (
                quantity_g * (new_value * new_factor) / (old_value * old_factor),
                new_value,
                new_unit,
            )

    # Case 3: the new unit is a mass unit -> absolute grams (new_value * factor).
    # Fallback when the previous value is zero or the old unit has no usable
    # conversion factor (e.g. ``item``, an unknown unit, or a different dimension).
    if new_standard_unit == "g" and new_factor is not None:
        return new_value * new_factor, new_value, new_unit

    # Case 4: any other unit change (e.g. volume <-> mass).
    # TODO: call the Open Food Facts parse API to convert the unit.
    raise exceptions.UnitConversionNotSupportedError(
        f"Converting from unit '{old_unit}' to unit '{new_unit}' is not supported yet."
    )


async def _quantity_from_mass_unit(value: float, unit_id: str, lang: str) -> float | None:
    f"""Compute the quantity in grams for a mass unit, or ``None`` if not a mass unit.

    Returns ``value * conversion_factor`` when ``unit_id`` is a taxonomy unit whose
    ``standard_unit`` is ``"g"`` and that defines a ``conversion_factor``.
    Returns ``None`` for the ``{types.ITEM_UNIT}`` sentinel or any non-mass (e.g. volume) unit.

    ``unit_id`` may be a taxonomy id or a localized unit name; names are resolved
    to their taxonomy id using ``lang`` (and the neutral ``xx`` language).

    :raises exceptions.UnknownUnitError: if ``unit_id`` is not in the units taxonomy
        (neither a known id nor a resolvable name) and is not the ``{types.ITEM_UNIT}``
        sentinel.
    """
    if unit_id == types.ITEM_UNIT:
        return None
    standard_unit, conversion_factor = await _unit_conversion(unit_id, lang)
    if standard_unit == "g" and conversion_factor is not None:
        return value * conversion_factor
    return None


async def _unit_conversion(unit_id: str, lang: str) -> tuple[str | None, float | None]:
    """Look up a unit's ``standard_unit`` and ``conversion_factor`` in the OFF taxonomy.

    ``unit_id`` may be a taxonomy id (e.g. ``xx:kg``) or a localized unit name
    (e.g. ``"kg"``); names are resolved to their taxonomy id using ``lang`` (and
    the neutral ``xx`` language) before the lookup.

    :raises exceptions.UnknownUnitError: if ``unit_id`` is neither a known taxonomy
        id nor a resolvable unit name.
    """
    units_taxonomy = await off.get_units_taxonomy()
    if unit_id not in units_taxonomy:
        # not a taxonomy id: try to resolve it as a localized unit name
        resolved = await _resolve_unit_name(unit_id, lang)
        if resolved is None:
            raise exceptions.UnknownUnitError(f"Unit '{unit_id}' is not a known unit.")
        unit_id = resolved
    node = units_taxonomy[unit_id]
    standard_unit = off._property_value(node, "standard_unit")
    factor_raw = off._property_value(node, "conversion_factor")
    conversion_factor = float(factor_raw) if factor_raw is not None else None
    return standard_unit, conversion_factor


async def _safe_unit_conversion(unit_id: str, lang: str) -> tuple[str | None, float | None]:
    f"""Like :func:`_unit_conversion` but returns ``(None, None)`` instead of raising.

    Used for the *old* unit in :func:`recompute_quantity`: it may be the
    ``{types.ITEM_UNIT}`` sentinel or an unknown / unresolvable name, in which
    case the same-standard-unit optimization simply does not apply and we fall
    back to the other cases.
    """
    if unit_id == types.ITEM_UNIT:
        return None, None
    try:
        return await _unit_conversion(unit_id, lang)
    except exceptions.UnknownUnitError:
        return None, None


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
