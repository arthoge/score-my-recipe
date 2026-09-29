"""Logging configuration for the application.

Only the ``api`` logger namespace is configured here, so the verbosity of
application code can be tuned independently of third-party libraries (openfoodfacts,
httpx, ...) and of uvicorn's own loggers (whose access logs always stay at INFO).

Keeping ``propagate=True`` on the ``api`` logger lets records reach the root
logger as well, which is what pytest's ``caplog`` relies on (see
``tests/test_labels_bonus.py``).
"""

import logging

from api.settings import LogLevel, get_settings

#: Logger namespace for all application modules (each module declares it via
#: ``logging.getLogger(__name__)`` where ``__name__`` starts with ``api.``).
APP_LOGGER_NAME = "api"

#: Format of log records emitted by the application.
#:
#: A timestamped, levelled format keeps application logs consistent with
#: uvicorn's timestamped output in the same stream.
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _level_value(level: LogLevel) -> int:
    """Return the numeric :mod:`logging` level for a :class:`LogLevel`.

    The enum values are lowercase names (eg. ``"warning"``) matching the
    standard :mod:`logging` level names, so a simple upper-case lookup works.
    """
    return getattr(logging, level.value.upper())


def setup_logging(level: LogLevel | None = None) -> None:
    """Configure the ``api`` logger with the given (or configured) level.

    A single :class:`~logging.StreamHandler` is attached, with records
    formatted by :data:`_LOG_FORMAT`. The call is idempotent: existing
    handlers on the ``api`` logger are cleared first, so repeated invocations
    (eg. across lifespan restarts or in tests) never accumulate duplicates.

    ``level`` defaults to :func:`api.settings.get_settings`'s ``log_level``
    when not provided, so the application level follows the
    ``SCORE_MY_RECIPE_LOG_LEVEL`` setting out of the box.
    """
    if level is None:
        level = get_settings().log_level

    logger = logging.getLogger(APP_LOGGER_NAME)
    # Clear any previously attached handlers to keep the call idempotent.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)

    logger.setLevel(_level_value(level))
    # Keep propagation so caplog (root-level) and third-party root handlers
    # still receive application records.
    logger.propagate = True
