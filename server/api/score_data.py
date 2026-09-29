"""Data useful for green-score computation."""

import csv
import io
import logging

from aiofile import async_open
from async_lru import alru_cache as async_cache

import api.settings as settings
from api import off

logger = logging.getLogger(__name__)

# A dict associating labels to their bonus in the green-score computation.
# see https://docs.score-environnemental.com/methodologie-recette/bonus-malus-recette/systeme-de-production/labels
LABELS_BONUS = {
    "fr:nature-et-progres": 20,
    "fr:bio-coherence": 20,
    "en:demeter": 20,
    "fr:bio-equitable": 20,
    "en:eu-organic": 15,
    "fr:ab-agriculture-biologique": 15,
    # TODO: Needs verification.
    # it's there:
    # https://docs.score-environnemental.com/methodologie/produit/systeme-de-production/label
    # but not there:
    # https://docs.score-environnemental.com/methodologie-recette/bonus-malus-recette/systeme-de-production/labels
    "en:sustainable-fishing-method": 15,
    "fr:haute-valeur-environnementale": 10,
    "en:utz-certified": 10,
    "en:rainforest-alliance": 10,
    "en:fairtrade-international": 10,
    "fr:bleu-blanc-coeur": 10,
    # this one is conditionned by the ingredient type, see LABELS_BONUS_INGREDIENTS_RESTRICTIONS
    "fr:label-rouge": 10,
    "en:sustainable-seafood-msc": 10,
    "en:responsible-aquaculture-asc": 10,
}


# A dict that restrict some labels bonus to specific ingredients types
LABELS_BONUS_INGREDIENTS_RESTRICTIONS = {
    "fr:label-rouge": ["en:beef", "en:veal-meat", "en:lamb-meat"],
}


@async_cache(maxsize=1)
async def get_epi_modifiers():
    """return a dict mapping origins to EPI bonuses

    see https://docs.score-environnemental.com/methodologie-recette/bonus-malus-recette/systeme-de-production/origine/synthese

    Note that it's not the same as for products !
    """
    fpath = settings.get_settings().data_dir / "greenscore-epi-bonuses.csv"
    # async read, then use csv.DictReader (which does not support async)
    async with async_open(fpath, "r", encoding="utf-8") as f:
        content = await f.read()
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    scores = {row["origin"].strip(): float(row["bonus"]) for row in reader if row["origin"].strip()}
    # add children
    origins_taxonomy = await off.get_origins_taxonomy()
    for origin, modifier in list(scores.items()):
        # origin is a taxonomy id, get its children
        try:
            origin_node = origins_taxonomy[origin]
        except KeyError:
            logger.warning(f"Origin {origin} found in epi modifiers csv but not found in taxonomy")
            origin_node = None
        if origin_node:
            for child in origin_node.get_children_hierarchy():
                # take worst modifier
                if child.id not in scores:
                    scores[child.id] = modifier
                else:
                    scores[child.id] = min(scores[child.id], modifier)
    return scores


# Distance modifier for worst case: no origin provided, or no country provided for recipe
DEFAULT_DISTANCE_MODIFIER = -7.0


@async_cache(maxsize=1)
async def get_distances_modifiers() -> dict[tuple[str, str], float]:
    """return a dict mapping origins to distance modifiers

    see https://docs.score-environnemental.com/methodologie-recette/bonus-malus-recette/origine

    the modifier for recepies corresponds to the (distance_score/10 - 7)

    """
    distances_modifiers = {}

    # First use the extended distance file, this is a distance score computed by Open Food Facts,
    # see https://wiki.openfoodfacts.org/Transportation_distances
    # it maps country code to country code
    fpath = settings.get_settings().data_dir / "greenscore-extended-distances-scores.csv"
    origins_by_country_code = await off.origins_by_country_code()
    async with async_open(fpath, "r", encoding="utf-8") as f:
        content = await f.read()
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        row_origin_id = origins_by_country_code.get(row["ISO Country Code"].upper())
        if row_origin_id is None:
            logger.warning(
                f"Origin for country code {row['ISO Country Code']} not found in taxonomy, skipping"
            )
            continue
        # map to every origin that has this country code
        for country_code, distance_score in row.items():
            # there are other columns names, but we only care about the country code ones
            origin_id = origins_by_country_code.get(country_code.upper())
            if origin_id and distance_score and distance_score.strip():
                # distance modifier between the two origins
                distances_modifiers[(origin_id, row_origin_id)] = float(distance_score) / 10.0 - 7.0

    # then add values from the more official source, this directly uses taxonomy ids (but it's less complete)
    fpath = settings.get_settings().data_dir / "greenscore-distances-scores.csv"
    # async read, then use csv.DictReader (which does not support async)
    async with async_open(fpath, "r", encoding="utf-8") as f:
        content = await f.read()
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        row_origin_id = row["origin"].strip()
        for origin_id, distance_score in row.items():
            # only origin identifiers
            if not origin_id.startswith("en:"):
                continue
            if distance_score.strip():
                distances_modifiers[(origin_id, row_origin_id)] = float(distance_score) / 10 - 7
    return distances_modifiers


async def warmup(lang: str) -> None:
    """Pre-populate the green-score modifier tables.

    ``lang`` is accepted for a uniform warmup signature but ignored: the EPI and
    distance modifier tables are language-independent. Both rely on the OFF
    origins taxonomy (warmed by :func:`api.off.warmup`), so this module is warmed
    after ``off`` in the orchestrator's dependency order.
    """
    # Lazy import breaks the otherwise circular dependency with api.warmup.
    from api.warmup import gather_warmup

    await gather_warmup(
        lang,
        {
            "score_data.get_epi_modifiers": get_epi_modifiers(),
            "score_data.get_distances_modifiers": get_distances_modifiers(),
        },
    )
