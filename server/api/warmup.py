"""Startup cache warmup orchestration.

Several business-logic methods are memoized (``async_lru`` / module globals) so
that only the very first request for a given language pays the cost of building
the cache. In production this first-user latency is undesirable, so the
``SCORE_MY_RECIPE_WARMUP`` setting (a comma-separated list of language codes)
triggers an upfront warmup at FastAPI startup.

Each module that owns warmable caches exposes ``async def warmup(lang: str)``.
(language independent warmup can ignore it).
This :func:`warmup` orchestrator is the single place that knows which modules
participate and in which order (dependency order: taxonomies and Agribalyse data
first, then the derived caches, then the per-language views).

Warmup is best-effort: every individual cached call is wrapped so that a single
failure (e.g. OpenFoodFacts unreachable) is logged and does not abort the rest.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from api.lang import two_letter_lang_code

logger = logging.getLogger(__name__)


async def gather_warmup(lang: str, calls: dict[str, Coroutine[Any, Any, Any]]) -> None:
    """Run a batch of warmup coroutines concurrently, logging any failure.

    Each call is independent: ``asyncio.gather`` is used with
    ``return_exceptions=True`` so a failure in one call is logged (at warning
    level, with the call name and language) without cancelling the others. The
    corresponding cache simply stays cold for that piece, exactly as it would
    without warmup.
    """
    results = await asyncio.gather(*calls.values(), return_exceptions=True)
    for name, result in zip(calls.keys(), results, strict=True):
        if isinstance(result, BaseException):
            logger.warning("Warmup of %s failed (lang=%s): %r", name, lang, result, exc_info=False)


# Modules owning warmable caches, in dependency order.
#
# ``off``    loads the raw taxonomies and the derived origins/language mappings.
# ``score_data`` builds the EPI/distance modifier tables (depend on off origins).
# ``score``  builds the label-bonus tables (depend on off label/ingredient taxonomies).
# ``agribalyse`` parses the Agribalyse CSV into lookup indexes (no lang dependency).
# ``recipes`` builds the per-language taxonomy views (depend on off + score_data + agribalyse).
# ``units``   builds the per-language unit views (depend on off units taxonomy).
#
# Imported here (and not at the top of each module) to keep this file the single
# source of truth for the participating set; modules do not import this module at
# load time, so there is no import cycle.
def _warmup_modules() -> list[Any]:
    import api.agribalyse as agribalyse
    import api.off as off
    import api.recipes as recipes
    import api.score as score
    import api.score_data as score_data
    import api.units as units

    return [off, score_data, score, agribalyse, recipes, units]


async def warmup(langs: list[str]) -> None:
    """Pre-populate caches for the given language codes.

    Language codes are normalized to their 2-letter form (e.g. ``"fr-FR"`` ->
    ``"fr"``) and de-duplicated while preserving order. For each language, every
    participating module's :func:`warmup` is awaited in dependency order. A
    failing module is logged and skipped so the others still warm up.
    """
    normalized = [two_letter_lang_code(lang) for lang in langs]
    seen: set[str] = set()
    unique_langs = [lang for lang in normalized if not (lang in seen or seen.add(lang))]

    modules = _warmup_modules()
    for lang in unique_langs:
        logger.info("Warming up caches for lang=%s", lang)
        for module in modules:
            try:
                await module.warmup(lang)
            except Exception:
                # Per-call failures are already handled inside each module's
                # warmup via gather_warmup; this guards against an unexpected
                # error in a module's warmup logic itself.
                logger.warning(
                    "Warmup of module %s failed (lang=%s)", module.__name__, lang, exc_info=True
                )
        logger.info("Warmup complete for lang=%s", lang)
