"""Agribalyse data storage, loading and ingredient-to-row matching.

This module is the single owner of *how* Agribalyse data is acquired and stored,
so that the backing format (currently a CSV built from the official XLSX export)
can be swapped out later without touching the rest of the codebase.

The Agribalyse Synthese data holds one row per food, identified by two codes:

* the first column ``code``:        the Agribalyse code
* the second column ``ciqual_code``: the Ciqual food code

To match an ingredient, we look up its taxonomy properties (searched on the
node then all its parents) in priority order. Properties prefixed with
``agribalyse_`` match the first column, those prefixed with ``ciqual_`` match
the second column.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

import openfoodfacts.taxonomy as taxonomy
import openpyxl

from api.settings import get_settings
from api.off import _node_chain, _property_value


logger = logging.getLogger(__name__)

# Column holding the Agribalyse code in the CSV.
AGRIBALYSE_CODE_COLUMN = "code"
# Column holding the Ciqual food code in the CSV.
CIQUAL_CODE_COLUMN = "ciqual_code"

# --- Agribalyse data source ------------------------------------------------

# Hardcoded Agribalyse data source (persistent DOI handle on the French
# research data repository).
SOURCE_URL = (
    "https://entrepot.recherche.data.gouv.fr/api/access/datafile/"
    ":persistentId?persistentId=doi:10.57745/JPY8JS"
)
# Name of the XLSX sheet holding the consolidated Synthese data.
SYNTHESE_SHEET = "Synthese"
# Row (1-indexed) of the first data line in the Synthese sheet (the header sits
# two rows above it).
FIRST_DATA_ROW = 5


# --- Schema -----------------------------------------------------------------


def _text(value: str | None) -> str:
    """Convert a CSV cell into a stripped string (``""`` for blank values)."""
    return (value or "").strip()


def _number(value: str | None) -> Optional[float]:
    """Convert a CSV cell into a float, returning ``None`` for blank values."""
    if value is None:
        return None
    value = value.strip()
    return float(value) if value else None


# Mapping of CSV column name -> conversion callable used to turn the raw CSV
# string into a typed value. The insertion order defines the column order of
# the stored file, so this dict *is* the schema of the Agribalyse storage.
HEADERS: dict[str, Callable[[str | None], Any]] = {
    "code": _text,
    "ciqual_code": _text,
    "group": _text,
    "subgroup": _text,
    "name_fr": _text,
    "lci_name": _text,
    "season_code": _text,
    "plane_code": _text,
    "delivery": _text,
    "packaging_approach": _text,
    "preparation": _text,
    "dqr": _number,
    "score": _number,
    "cc": _number,
    "ozone": _number,
    "ri": _number,
    "fpo": _number,
    "pm": _number,
    "htnhs": _number,
    "htchs": _number,
    "ated": _number,
    "eed": _number,
    "eem": _number,
    "eet": _number,
    "ecosystem_toxicity": _number,
    "land_use": _number,
    "water_use": _number,
    "energy_use": _number,
    "mineral_use": _number,
    "cc_biogenic": _number,
    "cc_fossil": _number,
    "cc_luc": _number,
}


def convert_row(raw: dict[str, str]) -> dict[str, Any]:
    """Convert a raw CSV string row into typed values using ``HEADERS``.

    Missing columns default to ``None`` so the converters handle blanks
    uniformly. Columns not part of the schema are dropped.
    """
    return {col: convert(raw.get(col)) for col, convert in HEADERS.items()}


# --- Fetch / build the CSV from the XLSX export -----------------------------


def is_xlsx(path: Path) -> bool:
    """Quick check that a file is really an XLSX (zip) archive."""
    try:
        with zipfile.ZipFile(path) as zf:
            return any(name.startswith("xl/") for name in zf.namelist())
    except (zipfile.BadZipFile, FileNotFoundError):
        return False


def download(url: str, dest: Path) -> None:
    """Download ``url`` into ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url} -> {dest}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as resp:
        with dest.open("wb") as fh:
            fh.write(resp.read())


def read_synthese(xlsx_path: Path) -> list[list]:
    """Read the ``Synthese`` sheet and return its data rows.

    The header (column names and order) is defined by :data:`HEADERS`, so only
    the data rows are returned. Empty rows are skipped.
    """
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    if SYNTHESE_SHEET not in wb.sheetnames:
        raise KeyError(
            f"No '{SYNTHESE_SHEET}' sheet in {xlsx_path.name} "
            f"(available: {', '.join(wb.sheetnames)})"
        )
    ws = wb[SYNTHESE_SHEET]
    data: list[list] = []
    for raw in ws.iter_rows(min_row=FIRST_DATA_ROW, values_only=True):
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw):
            continue  # skip empty rows
        data.append(list(raw))
    wb.close()
    return data


def write_csv(rows: list[list], out_path: Path) -> None:
    """Write ``rows`` to a CSV file using :data:`HEADERS` as the column header."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(HEADERS.keys()))
        writer.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {out_path}", file=sys.stderr)


def fetch_agribalyse(
    out_path: Path, cache_dir: Path, no_cache: bool = False, rebuild: bool = False
) -> int:
    """Download the Agribalyse XLSX and dump its Synthese sheet to a CSV.

    The XLSX is cached under ``cache_dir`` and re-used unless ``no_cache`` is
    set or the cached file is missing/invalid. Returns ``0`` on success,
    non-zero on error.
    """
    if out_path.exists() and not rebuild:
        print(f"  {out_path} already exists, skipping (use rebuild to overwrite)", file=sys.stderr)
        return 0
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "agribalyse.xlsx"
    if no_cache or not dest.exists() or not is_xlsx(dest):
        download(SOURCE_URL, dest)
    if not is_xlsx(dest):
        print(f"ERROR: {dest} is not a valid XLSX file", file=sys.stderr)
        return 1

    rows = read_synthese(dest)
    write_csv(rows, out_path)
    return 0


# --- Load the stored CSV into lookup indexes -------------------------------

# Lazy caches for the Agribalyse lookup tables, keyed by code column value.
_agribalyse_by_code: Optional[dict[str, dict[str, Any]]] = None
_agribalyse_by_ciqual: Optional[dict[str, dict[str, Any]]] = None


def _load_agribalyse() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load the Agribalyse CSV into two indexes (by code, by Ciqual code).

    Each raw CSV string row is converted to typed values through :data:`HEADERS`
    before being indexed. The result is cached for the lifetime of the process.
    """
    global _agribalyse_by_code, _agribalyse_by_ciqual
    if _agribalyse_by_code is not None and _agribalyse_by_ciqual is not None:
        return _agribalyse_by_code, _agribalyse_by_ciqual

    csv_path = get_settings().agribalyse_csv_path
    by_code: dict[str, dict[str, Any]] = {}
    by_ciqual: dict[str, dict[str, Any]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row = convert_row(raw)
            code = row[AGRIBALYSE_CODE_COLUMN]
            if code:
                by_code[code] = row
            ciqual = row[CIQUAL_CODE_COLUMN]
            if ciqual:
                by_ciqual[ciqual] = row
    logger.info(
        "Loaded %d Agribalyse rows (%d ciqual) from %s",
        len(by_code),
        len(by_ciqual),
        csv_path,
    )
    _agribalyse_by_code = by_code
    _agribalyse_by_ciqual = by_ciqual
    return by_code, by_ciqual


# --- Ingredient matching ----------------------------------------------------

# Taxonomy property names searched, in priority order, on each ingredient node
# and its parents. The CSV column is derived from the property prefix.
INGREDIENT_CODE_PROPERTIES: list[str] = [
    "agribalyse_food_code",
    "agribalyse_proxy_food_code",
    "ciqual_food_code",
    "ciqual_proxy_food_code",
]


def _column_for_property(prop: str) -> str:
    """Return the CSV column used to look up a code coming from `prop`."""
    if prop.startswith("agribalyse"):
        return AGRIBALYSE_CODE_COLUMN
    if prop.startswith("ciqual"):
        return CIQUAL_CODE_COLUMN
    raise ValueError(f"Unknown code property prefix: {prop!r}")


def get_row_by_code(code: str) -> Optional[dict[str, Any]]:
    """Resolve an explicitly chosen environmental reference by its Agribalyse code."""
    by_code, _ = _load_agribalyse()
    return by_code.get(code)


def get_reference_rows() -> list[dict[str, Any]]:
    """Return the existing catalog for food-reference searches."""
    by_code, _ = _load_agribalyse()
    return list(by_code.values())


def find_agribalyse_row(
    node: Optional[taxonomy.TaxonomyNode],
    search_parents: bool = True,
) -> tuple[Optional[str], Optional[str], Optional[dict[str, Any]]]:
    """Find the Agribalyse row matching a taxonomy node.

    The node's code properties are tried in priority order. When
    ``search_parents`` is ``True`` (the default) the same properties are also
    searched on the node's parents (closest first); when ``False`` only the
    node itself is considered — useful when walking down the taxonomy where a
    child should match on its own codes, not inherit a parent's.

    Returns ``(matched_code, code_source_property, row)`` where ``row`` is
    ``None`` when nothing matched.
    """
    if node is None:
        return None, None, None

    by_code, by_ciqual = _load_agribalyse()
    indexes = {AGRIBALYSE_CODE_COLUMN: by_code, CIQUAL_CODE_COLUMN: by_ciqual}

    # Nodes inspected for each property: the node alone, or the node followed
    # by its parents when parent search is enabled.
    nodes = [node] if not search_parents else _node_chain(node)

    for prop in INGREDIENT_CODE_PROPERTIES:
        column = _column_for_property(prop)
        index = indexes[column]
        for n in nodes:
            code = _property_value(n, prop)
            if code and code in index:
                return code, prop, index[code]
    return None, None, None


# --- Ingredient suggestions ------------------------------------------------


def suggest_scored_ingredient(
    node: Optional[taxonomy.TaxonomyNode],
) -> list[tuple[taxonomy.TaxonomyNode, str]]:
    """Suggest scored ingredient alternatives for a taxonomy node.

    Starting from ``node``, walk down the taxonomy (the ingredients taxonomy is
    a DAG, so a node may be reached through several parent paths) and collect
    every node that resolves to an Agribalyse row.

    A node is only reported when its matched Agribalyse row has a *different*
    ``code`` (row identity) than the rows already found along the current path:
    a child resolving to the same row as an already-reported ancestor brings no
    new information and is skipped. Recursion nonetheless continues past such
    skipped nodes, since a more specific descendant may resolve to a different
    row.

    Because the taxonomy is a DAG, the same node may finally be reported through
    several paths. A last cleaning pass drops any reported node when one of its
    taxonomy ancestors was itself reported with the same Agribalyse code (this
    removes duplicates that the per-path suppression could not catch).

    Returns a list of ``(node, agribalyse_row_code)`` tuples, each node
    appearing at most once.
    """
    if node is None:
        return []

    # Reported nodes, in DFS order. The same node may be appended more than once
    # if reached through several paths; it is deduplicated at the end.
    reported: list[tuple[taxonomy.TaxonomyNode, str]] = []
    # Memoization key (node id, ancestor codes) to bound traversal in the DAG.
    seen: set[tuple[str, frozenset[str]]] = set()

    def visit(current: taxonomy.TaxonomyNode, ancestor_codes: frozenset[str]) -> None:
        key = (current.id, ancestor_codes)
        if key in seen:
            return
        seen.add(key)

        # Only look at the node's own codes: a child must match on its own
        # properties, not inherit a parent's (that is the whole point of going
        # down the hierarchy).
        _, _, row = find_agribalyse_row(current, search_parents=False)
        row_code: Optional[str] = row["code"] if row is not None else None

        child_codes = ancestor_codes
        if row_code is not None and row_code not in ancestor_codes:
            reported.append((current, row_code))
            child_codes = ancestor_codes | {row_code}

        # Always recurse, even past a suppressed node: a deeper descendant may
        # resolve to a different Agribalyse row.
        for child in current.children:
            visit(child, child_codes)

    visit(node, frozenset())

    return _dedupe_reported(reported)


def _dedupe_reported(
    reported: list[tuple[taxonomy.TaxonomyNode, str]],
) -> list[tuple[taxonomy.TaxonomyNode, str]]:
    """Final cleaning of the reported alternatives.

    A node may appear several times (reached through several DAG paths); since a
    node always resolves to the same Agribalyse code, we keep its first
    occurrence. We then drop a node when one of its taxonomy ancestors was also
    reported with the same code — that ancestor is a strictly more general
    alternative already covered.
    """
    # First occurrence of each node id (codes are deterministic per node).
    first: dict[str, tuple[taxonomy.TaxonomyNode, str]] = {}
    for n, code in reported:
        first.setdefault(n.id, (n, code))

    result: list[tuple[taxonomy.TaxonomyNode, str]] = []
    for n, code in first.values():
        ancestor_ids = {p.id for p in n.get_parents_hierarchy()}
        # Drop if any *other* reported node with the same code is an ancestor.
        if any(
            other_id != n.id and other_code == code and other_id in ancestor_ids
            for other_id, (_, other_code) in first.items()
        ):
            continue
        result.append((n, code))
    return result


async def warmup(lang: str) -> None:
    """Pre-parse the Agribalyse CSV into lookup indexes.

    ``lang`` is ignored: the Agribalyse indexes are language-independent. This
    removes the first green-score / ingredients request latency and populates the
    lazy module global (:func:`_load_agribalyse`) upfront, avoiding a
    concurrent-load race when several languages are warmed. The (synchronous) CSV
    parse runs in a thread so it does not block the event loop.
    """
    # Lazy import breaks the otherwise circular dependency with api.warmup.
    from api.warmup import gather_warmup

    await gather_warmup(lang, {"agribalyse._load_agribalyse": asyncio.to_thread(_load_agribalyse)})
