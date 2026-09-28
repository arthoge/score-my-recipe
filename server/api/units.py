"""Units (as kg, ml, cups, etc) business logic."""

import logging
import unicodedata

from async_lru import alru_cache as async_lru_cache

import api.exceptions as exceptions
import api.off as off
import api.types as types
from api.lang import two_letter_lang_code

logger = logging.getLogger(__name__)


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

    Lowercases, strips surrounding whitespace, removes accents
    (e.g. ``"pièce"`` -> ``"piece"``) and replaces spaces with ``-``
    (so ``"fl oz"`` matches the ``"fl-oz"`` form used in taxonomy slugs).
    """
    no_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(char)
    )
    return no_accents.strip().casefold().replace(" ", "-")


@async_lru_cache(maxsize=200)
async def _unit_name_to_id(lang: str) -> dict[str, str]:
    """Cached mapping of normalized unit name -> taxonomy id, for ``lang`` and ``xx``.

    Built only from the units returned by :func:`_get_units_entries`
    (i.e. mass and volume units).
    Translations from both the requested ``lang`` (which already falls back to
    ``xx``/``en`` for missing entries) and the neutral ``xx`` language are merged,
    so language-neutral abbreviations such as ``"kg"`` (the ``xx`` name of
    ``xx:kg``) resolve regardless of the requested language.

    Both the canonical label and every synonym are used as keys.
    On a collision (a name shared by two units) the first-seen unit wins
    and a warning is logged.
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

    Probes the cached name->id mapping built from :func:`_get_units_entries`
    for ``lang`` (which already merges the neutral ``xx`` language,
    so abbreviations like ``"kg"`` resolve for any language).
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

    Units may be given either as a taxonomy id (e.g. ``xx:kg``),
    as a localized unit name (e.g. ``"kg"``) resolved through ``lang``
    (and the neutral ``xx`` language), or as the ``{types.ITEM_UNIT}`` sentinel
    for countable ingredients.
    The ``new_unit`` is only resolved when its conversion factor is actually
    needed (the unit cancels out in a plain cross-multiplication).
    The ``old_unit`` is only resolved when the units differ but share the same
    standard unit (so the grams can be cross-multiplied through it),
    otherwise it is only compared as-is to detect an unchanged unit.

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

    Returns ``value * conversion_factor`` when ``unit_id`` is a taxonomy unit
    whose ``standard_unit`` is ``"g"`` and that defines a ``conversion_factor``.
    Returns ``None`` for the ``{types.ITEM_UNIT}`` sentinel
    or any non-mass (e.g. volume) unit.

    ``unit_id`` may be a taxonomy id or a localized unit name;
    names are resolved to their taxonomy id using ``lang`` (and the neutral ``xx`` language).

    :raises exceptions.UnknownUnitError: if ``unit_id`` is not in the units taxonomy
        (neither a known id nor a resolvable name)
        and is not the ``{types.ITEM_UNIT}`` sentinel.
    """
    if unit_id == types.ITEM_UNIT:
        return None
    standard_unit, conversion_factor = await _unit_conversion(unit_id, lang)
    if standard_unit == "g" and conversion_factor is not None:
        return value * conversion_factor
    return None


async def _unit_conversion(unit_id: str, lang: str) -> tuple[str | None, float | None]:
    """Look up a unit's ``standard_unit`` and ``conversion_factor`` in the OFF taxonomy.

    ``unit_id`` may be a taxonomy id (e.g. ``xx:kg``) or a localized unit name (e.g. ``"kg"``);
    names are resolved to their taxonomy id using ``lang`` (and the neutral ``xx`` language)
    before the lookup.

    :raises exceptions.UnknownUnitError: if ``unit_id`` is neither a known taxonomy id
        nor a resolvable unit name.
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
    ``{types.ITEM_UNIT}`` sentinel or an unknown / unresolvable name,
    in which case the same-standard-unit optimization simply does not apply
    and we fall back to the other cases.
    """
    if unit_id == types.ITEM_UNIT:
        return None, None
    try:
        return await _unit_conversion(unit_id, lang)
    except exceptions.UnknownUnitError:
        return None, None
