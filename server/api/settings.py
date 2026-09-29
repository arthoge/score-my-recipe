from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class OpenFoodFactsEnvironments(StrEnum):
    """Enum for the OpenFoodFacts API environments."""

    PROD = "prod"
    STAGING = "staging"


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

    warmup: Annotated[
        list[str],
        NoDecode,
        Field(
            description=(
                "Comma-separated list of language codes to pre-warm at startup "
                "(e.g. 'fr,en'). When set, the relevant cached methods are called "
                "upfront for each language so the first user does not pay the cold-cache "
                "latency. Empty by default (no warmup)."
            ),
        ),
    ] = []

    @field_validator("warmup", mode="before")
    @classmethod
    def _split_warmup_csv(cls, value: str | None | list[str]) -> list[str]:
        """Parse the comma-separated ``WARMUP`` env value into a list of codes.

        ``NoDecode`` keeps pydantic-settings from JSON-decoding this list field
        from the environment (which would reject ``"fr,en"``), so the raw string
        reaches this validator. We split on commas, strip whitespace and drop
        empty entries. An already-typed list (e.g. passed in tests) is left as-is.
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [code.strip() for code in value.split(",") if code.strip()]
        return value


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
