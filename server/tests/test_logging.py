"""Tests for the application logging configuration.

Covers:
- the ``log_level`` setting (default, env override, enum validation),
- :func:`api.logging_config.setup_logging` behaviour (level applied, propagation
  kept, idempotency on repeated calls).
"""

from __future__ import annotations

import logging

import pytest

from api import logging_config
from api.settings import LogLevel, Settings
from api.settings import get_settings as _get_settings
import api.settings as settings_module


@pytest.fixture
def reset_api_logger():
    """Restore the ``api`` logger state after each test.

    setup_logging mutates the shared ``api`` logger (handlers, level), so the
    changes would otherwise leak across tests and into the global test run.
    """
    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    saved_handlers = logger.handlers[:]
    saved_level = logger.level
    saved_propagate = logger.propagate
    yield logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    for handler in saved_handlers:
        logger.addHandler(handler)
    logger.setLevel(saved_level)
    logger.propagate = saved_propagate


@pytest.fixture
def reset_settings():
    """Drop the cached Settings singleton around the test.

    get_settings() memoizes one instance, so env-based overrides would stick
    across tests without this reset.
    """
    saved = settings_module._settings
    settings_module._settings = None
    yield
    settings_module._settings = saved


# --- Settings -----------------------------------------------------------------


def test_log_level_defaults_to_info(reset_settings):
    """The log_level setting defaults to INFO when no env var is set."""
    settings = Settings()
    assert settings.log_level is LogLevel.INFO


@pytest.mark.parametrize(
    "env_value, expected",
    [
        ("debug", LogLevel.DEBUG),
        ("info", LogLevel.INFO),
        ("warning", LogLevel.WARNING),
        ("error", LogLevel.ERROR),
        ("critical", LogLevel.CRITICAL),
    ],
)
def test_log_level_read_from_env(monkeypatch, reset_settings, env_value, expected):
    """Each lowercase level is parsed into the matching LogLevel enum value."""
    monkeypatch.setenv("SCORE_MY_RECIPE_LOG_LEVEL", env_value)
    assert Settings().log_level is expected


def test_invalid_log_level_rejected(monkeypatch, reset_settings):
    """Unknown level values are rejected by the enum (no silent fallback)."""
    monkeypatch.setenv("SCORE_MY_RECIPE_LOG_LEVEL", "verbose")
    with pytest.raises(ValueError):
        Settings()


def test_log_level_used_when_setup_called_without_arg(reset_settings, reset_api_logger):
    """setup_logging() reads the configured log_level when none is passed."""
    monkeypatch_set_level = pytest.MonkeyPatch()
    monkeypatch_set_level.setenv("SCORE_MY_RECIPE_LOG_LEVEL", "warning")
    try:
        logging_config.setup_logging()
    finally:
        monkeypatch_set_level.undo()

    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    assert logger.level == logging.WARNING


# --- setup_logging -----------------------------------------------------------


def test_setup_logging_sets_api_level(reset_api_logger):
    """setup_logging applies the given level to the api logger."""
    logging_config.setup_logging(LogLevel.ERROR)
    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    assert logger.level == logging.ERROR


def test_setup_logging_keeps_propagation(reset_api_logger):
    """Propagation stays on so caplog (root-level) keeps receiving records."""
    logging_config.setup_logging(LogLevel.WARNING)
    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    assert logger.propagate is True


def test_setup_logging_attaches_single_handler(reset_api_logger):
    """Exactly one StreamHandler is attached, with the expected format."""
    logging_config.setup_logging(LogLevel.INFO)
    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    # The formatter must render the configured fields (level + name + message).
    record = logging.LogRecord(
        name="api.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatted = handler.format(record)
    assert "INFO" in formatted
    assert "api.test" in formatted
    assert "hello" in formatted


def test_setup_logging_is_idempotent(reset_api_logger):
    """Repeated calls never accumulate handlers."""
    logging_config.setup_logging(LogLevel.INFO)
    logging_config.setup_logging(LogLevel.WARNING)
    logging_config.setup_logging(LogLevel.DEBUG)
    logger = logging.getLogger(logging_config.APP_LOGGER_NAME)
    assert len(logger.handlers) == 1
    # The last call wins for the level.
    assert logger.level == logging.DEBUG


def test_setup_logging_does_not_touch_subloggers(reset_settings, reset_api_logger):
    """setup_logging only reconfigures the api namespace, not arbitrary loggers."""
    other = logging.getLogger("openfoodfacts")
    other.setLevel(logging.DEBUG)
    logging_config.setup_logging(LogLevel.WARNING)
    # An unrelated logger must keep its own level untouched.
    assert logging.getLogger("openfoodfacts").level == logging.DEBUG


# Sanity check: get_settings still works after the reset fixture restored state.
def test_get_settings_returns_instance():
    assert _get_settings() is _get_settings()
