"""Shared helpers and mocks for the green-score test suite."""

from contextlib import contextmanager
from typing import Iterable
from unittest.mock import AsyncMock, patch

from openfoodfacts.taxonomy import Taxonomy, TaxonomyNode

from api import types
from api.lang import two_letter_lang_code


# useful constant when computing scores without origins
WORLD_EPI_MODIFIER = -3.0

# useful constant when computing scores for France distance
FRANCE_DISTANCE_MODIFIER = 3


@contextmanager
def patch_language_check(valid_codes: Iterable[str] = ("en", "fr", "es", "it", "de")):
    """Patch ``api.checks.check_language_code`` to accept the given 2-letter codes.

    Mirrors the production check (which normalizes the code to its 2-letter form
    before looking it up in the OFF languages taxonomy) without hitting the
    network: a code is valid iff its normalized 2-letter form is in
    ``valid_codes``. This lets tests control which languages are accepted (and
    reject ``"zz"``) deterministically.
    """
    valid = set(valid_codes)

    async def check_language_code(lang: str) -> bool:
        return two_letter_lang_code(lang) in valid

    with patch(
        "api.checks.check_language_code",
        new_callable=AsyncMock,
        side_effect=check_language_code,
    ) as mock:
        yield mock


@contextmanager
def patch_ingredients_taxonomy(taxonomy):
    """Patch ``api.off.get_ingredients_taxonomy`` to return ``taxonomy``."""
    with patch("api.off.get_ingredients_taxonomy", new_callable=AsyncMock) as mock_tax:
        mock_tax.return_value = taxonomy
        yield mock_tax


@contextmanager
def patch_labels_taxonomy(taxonomy):
    """Patch ``api.off.get_labels_taxonomy`` to return ``taxonomy``.

    Also resets the ``labels_bonus_full`` cache so each test rebuilds the bonus
    table from the provided (mocked) taxonomy.
    """
    import api.score as score

    score.labels_bonus_full.cache_clear()
    try:
        with patch("api.off.get_labels_taxonomy", new_callable=AsyncMock) as mock_tax:
            mock_tax.return_value = taxonomy
            yield mock_tax
    finally:
        score.labels_bonus_full.cache_clear()


@contextmanager
def patch_origins_taxonomy(taxonomy):
    """Patch ``api.off.get_origins_taxonomy`` to return ``taxonomy``.

    Also resets the ``get_epi_modifiers`` cache so each test rebuilds the
    modifiers table using the provided (mocked) taxonomy.
    """
    import api.score_data as score_data

    score_data.get_epi_modifiers.cache_clear()
    try:
        with patch("api.off.get_origins_taxonomy", new_callable=AsyncMock) as mock_tax:
            mock_tax.return_value = taxonomy
            yield mock_tax
    finally:
        score_data.get_epi_modifiers.cache_clear()


@contextmanager
def patch_epi_modifiers(modifiers: dict[str, float]):
    """Patch ``api.score_data.get_epi_modifiers`` to return ``modifiers``.

    Also resets the ``get_epi_modifiers`` cache so each test rebuilds the
    modifiers from the provided (mocked) mapping.
    """
    import api.score_data as score_data

    score_data.get_epi_modifiers.cache_clear()
    try:
        with patch("api.score_data.get_epi_modifiers", new_callable=AsyncMock) as mock_mods:
            mock_mods.return_value = modifiers
            yield mock_mods
    finally:
        score_data.get_epi_modifiers.cache_clear()


def create_taxonomy_node(
    id: str,
    properties: dict | None = None,
    names: dict[str, str] | None = None,
    synonyms: dict[str, list[str]] | None = None,
    parents: list[TaxonomyNode] | None = None,
    children: list[TaxonomyNode] | None = None,
) -> TaxonomyNode:
    """Build a real ``TaxonomyNode`` with a test-friendly constructor.

    Wraps ``openfoodfacts.taxonomy.TaxonomyNode`` so that the parent/child
    hierarchy methods (``get_parents_hierarchy``, ``get_children_hierarchy`` …)
    used by the production code come from the library itself.

    :param id: the node identifier (e.g. ``"en:apple"``)
    :param properties: optional properties dict stored on the node
    :param parents: optional direct parents; wired up via ``add_parents`` so
        that the ``children`` back-reference is set automatically
    :param children: optional direct children; each child gets ``self`` added
        as a parent
    """
    node = TaxonomyNode(
        identifier=id,
        names=names or {},
        synonyms=synonyms or None,
        properties=properties or {},
    )
    if parents:
        node.add_parents(parents)
    if children:
        for child in children:
            child.add_parents([node])
    return node


def create_taxonomy(nodes: list[TaxonomyNode] | dict[str, TaxonomyNode]) -> Taxonomy:
    """Build a real ``Taxonomy`` pre-populated with ``nodes``.

    The returned object supports ``in``, ``[…]`` indexing and ``iter_nodes``
    exactly like a taxonomy fetched from OpenFoodFacts.
    """
    taxonomy = Taxonomy()
    if isinstance(nodes, list):
        nodes = {node.id: node for node in nodes}
    for key, node in nodes.items():
        taxonomy.add(key, node)
    return taxonomy


def build_label_obj(id_: str, label: str | None = None) -> types.TaxonomyItem:
    """Build a ``TaxonomyItem`` representing an ingredient label."""
    return types.TaxonomyItem(id=id_, label=label or id_, is_in_taxonomy=True)


def build_ingredient_dict(
    id_: str,
    name: str,
    taxonomy_id: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    """Build a frontend-shaped (camelCase) ingredient JSON object."""
    return {
        "id": id_,
        "name": name,
        "weight": 100,
        "codifiedIngredient": (
            {"id": taxonomy_id, "label": name, "isInTaxonomy": True} if taxonomy_id else None
        ),
        "labels": [{"id": lid, "label": lid, "isInTaxonomy": True} for lid in (labels or [])],
        "isInSeason": False,
        "isFreshPlant": False,
        "origin": None,
    }


def build_origin_obj(origin_id: str, label: str | None = None) -> types.TaxonomyItem:
    """Build a ``TaxonomyItem`` representing an ingredient origin."""
    return types.TaxonomyItem(id=origin_id, label=label or origin_id, is_in_taxonomy=True)


def build_ingredient_obj(
    id_: str,
    name: str,
    taxonomy_id: str | None = None,
    weight: float = 100.0,
    labels: list[str] | None = None,
    origin: str | None = None,
    is_fresh_plant: bool = False,
    is_in_season: bool = False,
) -> types.RecipeIngredientInput:
    """Build a ``RecipeIngredientInput`` with a codified ingredient.

    When ``taxonomy_id`` is ``None``, the codified ingredient is a free-text
    entry (``id=None``, ``is_in_taxonomy=False``).

    :param taxonomy_id: taxonomy id of the codified ingredient, or ``None`` for
        a free-text entry
    :param origin: optional origin taxonomy id (e.g. ``"en:france"``)
    :param is_fresh_plant: whether the ingredient is a fresh fruit/vegetable
    :param is_in_season: whether the ingredient is in season (only meaningful
        when ``is_fresh_plant`` is true)
    """
    return types.RecipeIngredientInput(
        id=id_,
        name=name,
        weight=weight,
        codified_ingredient=types.TaxonomyItem(
            id=taxonomy_id,
            label=name,
            is_in_taxonomy=taxonomy_id is not None,
        ),
        labels=[build_label_obj(lid) for lid in (labels or [])],
        is_fresh_plant=is_fresh_plant,
        is_in_season=is_in_season,
        origin=build_origin_obj(origin) if origin else None,
    )
