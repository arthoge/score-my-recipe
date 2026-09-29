from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenFoodFactsEnvironments(StrEnum):
    """Enum for the OpenFoodFacts API environments."""

    PROD = "prod"
    STAGING = "staging"


class LogLevel(StrEnum):
    """Enum for the application logging levels.

    Values are lowercase so the corresponding ``SCORE_MY_RECIPE_LOG_LEVEL``
    environment variable stays readable (eg. ``warning``), mirroring the
    casing convention of :class:`OpenFoodFactsEnvironments`.
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCORE_MY_RECIPE_")

    data_dir: Annotated[Path, Field(description="Directory where data is stored")] = Path("./data")

    cache_dir: Annotated[Path, Field(description="Directory where cache is stored")] = Path(
        "./data/cache"
    )

    agribalyse_csv_path: Annotated[
        Path, Field(description="Path to the merged Agribalyse Synthese CSV file")
    ] = Path("./data/agribalyse.csv")

    openfoodfacts_env: Annotated[
        OpenFoodFactsEnvironments,
        Field(description="Environment to use for OpenFoodFacts API (prod or staging)"),
    ] = OpenFoodFactsEnvironments.PROD

    log_level: Annotated[
        LogLevel,
        Field(
            description=(
                "Application logging level (debug, info, warning, error, critical). "
                "Defaults to info; should be set to warning on staging and prod "
                "to reduce log verbosity."
            ),
        ),
    ] = LogLevel.INFO


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
