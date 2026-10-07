"""This module provides different helper commands"""

from pathlib import Path

import typer

cli = typer.Typer()


@cli.command()
def ping():
    # just a command so that export-openapi is not "run"
    print("pong")


@cli.command()
def fetch_ciqual():
    """Regenerate the bundled food catalog from the pinned ANSES CIQUAL 2025 release."""
    from api.ciqual import fetch_catalog

    fetch_catalog()


@cli.command()
def fetch_ciqual_nutrients():
    """Regenerate the pinned CIQUAL 2025 nutrient composition catalog."""
    from api.nutrition_data import fetch_catalog

    fetch_catalog()


@cli.command()
def export_openapi(
    target_path: Path = typer.Argument(
        exists=False,
        file_okay=True,
        dir_okay=False,
        help="Path of the YAML or JSON data file",
    ),
):
    """Export OpenAPI specification to a file."""
    import json
    import yaml

    import sys

    # add server/ to path
    sys.path.append(str(Path(__file__).parent.parent))

    from api import api

    openapi = api.app.openapi()
    version = openapi.get("openapi", "unknown version")

    print(f"writing openapi spec v{version}")
    with open(target_path, "w") as f:
        if str(target_path).endswith(".json"):
            json.dump(openapi, f, indent=2)
        else:
            yaml.dump(openapi, f, sort_keys=False)

    print(f"spec written to {target_path}")


@cli.command()
def fetch_agribalyse(
    out: Path = typer.Option(Path("data/agribalyse.csv"), help="Output CSV file path."),
    cache_dir: Path = typer.Option(
        Path("data/cache"), help="Directory where the downloaded XLSX is cached."
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help=(
            "Force re-download of the XLSX export.\n"
            "Note that if the CSV is already generated and --rebuild is not set, "
            "the XLSX will not be downloaded."
        ),
    ),
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Rebuild CSV file even if it already exists."
    ),
):
    """Download the Agribalyse XLSX export and rebuild the Synthese CSV.

    The heavy lifting lives in :mod:`api.agribalyse`; this command only wires
    the options through.
    """
    import sys

    # add server/ to path so `api` is importable when run as a script
    sys.path.append(str(Path(__file__).parent.parent))

    from api import agribalyse

    raise SystemExit(agribalyse.fetch_agribalyse(out, cache_dir, no_cache, rebuild))


def main() -> None:
    cli()
