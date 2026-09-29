"""Tests for startup cache warmup: settings parsing, the orchestrator and the
per-module ``warmup`` functions.

All cached functions are mocked (no network): the goal is to verify that warmup
calls the right functions, in the right dependency order, and is fault-tolerant.
"""

import logging
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from api import agribalyse, off, recipes, score, score_data, units
from api.settings import Settings
from api.warmup import gather_warmup, warmup

# Modules participating in warmup, in the orchestrator's dependency order.
WARMUP_MODULES = ["off", "score_data", "score", "agribalyse", "recipes", "units"]


# --- Settings CSV parsing --------------------------------------------------


def test_settings_warmup_splits_comma_separated_string():
    assert Settings(warmup="fr,en").warmup == ["fr", "en"]  # ty: ignore[invalid-argument-type]


def test_settings_warmup_strips_whitespace_and_drops_empties():
    assert Settings(warmup=" fr , ,en ").warmup == ["fr", "en"]  # ty: ignore[invalid-argument-type]


def test_settings_warmup_empty_string_yields_empty_list():
    assert Settings(warmup="").warmup == []  # ty: ignore[invalid-argument-type]


def test_settings_warmup_none_yields_empty_list():
    assert Settings(warmup=None).warmup == []  # ty: ignore[invalid-argument-type]


def test_settings_warmup_default_is_empty():
    assert Settings().warmup == []


def test_settings_warmup_accepts_already_typed_list():
    assert Settings(warmup=["fr", "en"]).warmup == ["fr", "en"]


def test_settings_warmup_reads_env_var(monkeypatch):
    """The comma-separated env var is parsed into a list (not JSON-decoded)."""
    monkeypatch.setenv("SCORE_MY_RECIPE_WARMUP", "fr,en")
    assert Settings().warmup == ["fr", "en"]


def test_settings_warmup_env_var_empty(monkeypatch):
    monkeypatch.setenv("SCORE_MY_RECIPE_WARMUP", "")
    assert Settings().warmup == []


# --- gather_warmup helper --------------------------------------------------


@pytest.mark.asyncio
async def test_gather_warmup_logs_failure_and_continues(caplog):
    """A failing call is logged and does not cancel the others."""

    async def boom() -> None:
        raise RuntimeError("taxonomy down")

    ok = AsyncMock()
    with caplog.at_level(logging.WARNING):
        await gather_warmup("fr", {"boom": boom(), "ok": ok()})

    ok.assert_awaited_once()
    assert any("boom" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_gather_warmup_succeeds_when_all_calls_pass():
    a = AsyncMock()
    b = AsyncMock()
    await gather_warmup("en", {"a": a(), "b": b()})
    a.assert_awaited_once()
    b.assert_awaited_once()


# --- Orchestrator ----------------------------------------------------------


@pytest.mark.asyncio
async def test_warmup_calls_each_module_per_lang_in_dependency_order():
    """Each module's warmup is called once per language, in dependency order."""
    order: list[tuple[str, str]] = []

    def recorder(name: str):
        async def _warmup(lang: str) -> None:
            order.append((name, lang))

        return _warmup

    with ExitStack() as stack:
        for name in WARMUP_MODULES:
            stack.enter_context(patch(f"api.{name}.warmup", new=recorder(name)))
        await warmup(["fr", "en"])

    expected = [(m, lang) for lang in ("fr", "en") for m in WARMUP_MODULES]
    assert order == expected


@pytest.mark.asyncio
async def test_warmup_normalizes_and_deduplicates_languages():
    """Language codes are normalized (fr-FR -> fr) and de-duplicated."""
    calls: list[str] = []

    async def _warmup(lang: str) -> None:
        calls.append(lang)

    with ExitStack() as stack:
        for name in WARMUP_MODULES:
            stack.enter_context(patch(f"api.{name}.warmup", new=_warmup))
        await warmup(["fr-FR", "fr", "en"])

    # "fr-FR" normalized to "fr" and merged with the explicit "fr": each of the
    # 6 modules is called once with "fr" and once with "en".
    assert calls.count("fr") == len(WARMUP_MODULES)
    assert calls.count("en") == len(WARMUP_MODULES)
    assert "fr-FR" not in calls


@pytest.mark.asyncio
async def test_warmup_continues_when_a_module_raises():
    """A failing module is skipped so the others still warm up."""
    called: list[str] = []

    async def boom(lang: str) -> None:
        raise RuntimeError("off down")

    async def ok(lang: str) -> None:
        called.append(lang)

    with ExitStack() as stack:
        # off is first in dependency order and fails; the rest must still run.
        stack.enter_context(patch("api.off.warmup", new=boom))
        for name in WARMUP_MODULES[1:]:
            stack.enter_context(patch(f"api.{name}.warmup", new=ok))
        await warmup(["fr"])

    assert called == ["fr"] * (len(WARMUP_MODULES) - 1)


@pytest.mark.asyncio
async def test_warmup_empty_list_does_nothing():
    """An empty language list calls no module warmup."""
    mocks = {name: AsyncMock() for name in WARMUP_MODULES}
    with ExitStack() as stack:
        for name, m in mocks.items():
            stack.enter_context(patch(f"api.{name}.warmup", new=m))
        await warmup([])
    for m in mocks.values():
        m.assert_not_called()


# --- Per-module warmup -----------------------------------------------------


async def _assert_warmup_invokes(module, func_names, lang="fr"):
    """Run ``module.warmup(lang)`` with the named functions mocked and assert
    each is awaited exactly once.
    """
    mocks = {name: AsyncMock() for name in func_names}
    with patch.multiple(module.__name__, **mocks):
        await module.warmup(lang)
    for name, mock in mocks.items():
        assert mock.await_count == 1, f"{module.__name__}.{name} awaited {mock.await_count} times"


@pytest.mark.asyncio
async def test_off_warmup_invokes_all_cached_functions():
    await _assert_warmup_invokes(
        off,
        [
            "get_origins_taxonomy",
            "get_ingredients_taxonomy",
            "get_units_taxonomy",
            "get_labels_taxonomy",
            "get_countries_taxonomy",
            "get_languages_taxonomy",
            "origins_by_country_code",
            "languages_by_code",
            "origin_to_country_origin",
        ],
    )


@pytest.mark.asyncio
async def test_score_data_warmup_invokes_modifier_tables():
    await _assert_warmup_invokes(score_data, ["get_epi_modifiers", "get_distances_modifiers"])


@pytest.mark.asyncio
async def test_score_warmup_invokes_label_bonus_tables():
    await _assert_warmup_invokes(
        score, ["labels_bonus_full", "labels_bonus_ingredients_restrictions_full"]
    )


@pytest.mark.asyncio
async def test_recipes_warmup_invokes_per_lang_views():
    await _assert_warmup_invokes(
        recipes,
        [
            "_get_origins_entries",
            "_get_labels_entries",
            "get_countries_entries",
            "_get_ingredients_entries",
        ],
        lang="fr",
    )


@pytest.mark.asyncio
async def test_units_warmup_invokes_units_views():
    await _assert_warmup_invokes(units, ["_get_units_entries", "_unit_name_to_id"], lang="fr")


@pytest.mark.asyncio
async def test_agribalyse_warmup_loads_csv():
    """agribalyse.warmup pre-parses the CSV via _load_agribalyse (in a thread).

    _load_agribalyse is synchronous, so a regular MagicMock is used (it runs in
    a worker thread through asyncio.to_thread, not awaited directly).
    """
    with patch("api.agribalyse._load_agribalyse") as mock_load:
        await agribalyse.warmup("fr")
    mock_load.assert_called_once()
