# CIQUAL food identities

`ciqual-foods-2025.json` contains the 3,484 food codes and official French/English
names from ANSES's CIQUAL 2025 food list. It contains food identities only;
nutrient composition is stored separately in the catalog described below.

Source: ANSES, *Table de composition nutritionnelle des aliments Ciqual 2025*,
[`alim_2025_11_03.xml`](https://entrepot.recherche.data.gouv.fr/api/access/datafile/666252),
[dataset DOI: 10.57745/RDMHWY](https://doi.org/10.57745/RDMHWY).
License: [Licence Ouverte / Open Licence 2.0](https://spdx.org/licenses/etalab-2.0.html).
The derived catalog trims XML whitespace and retains original codes and names.

The source URL and SHA-256 checksum are pinned in `api/ciqual.py`. Regenerate
the catalog from the `server` directory:

```sh
uv run typer api/cli.py run fetch-ciqual
```

## Nutrient composition

`ciqual-nutrients-2025.json` contains the eight recipe-analysis nutrients for all
3,484 official foods, plus the official food groups used to identify eligible
plant ingredients. Source values are retained, including missing values, traces,
and quantified upper limits. Energy follows EU 1169/2011 and protein uses N×6.25.

Source: [ANSES Ciqual 2025 workbook](https://entrepot.recherche.data.gouv.fr/api/access/datafile/666260),
from the same DOI and Open Licence 2.0 dataset above. SHA-256:
`5555c572fa3735991298d832d0427788fa69a11b4fd20a5d580d58942369fbb0`.
Rebuild with `uv run typer api/cli.py run fetch-ciqual-nutrients`.

`POST /v1/nutrition/analyze` aggregates complete served-component composition.
OFF barcodes take precedence over a generic Ciqual selection, without silently
replacing a product if lookup fails. Supported dry-food boiling profiles use
Ciqual counterparts 9125 (basmati rice), 9822 (dried egg pasta) and 20360 (lentils).
Steamed potato weight estimation has no matching reviewed nutrition counterpart
and is not automatically supported for nutrition. No retention correction is
applied a second time to prepared composition.

Missing and unquantified trace values stay unknown. Quantified `< x` values use
conservative bounds (x for unfavorable nutrients, zero for fiber/protein), with
an assumption in the response. Unknown composite/concentrated plant proportions,
unsupported cooking and incomplete nutrients prevent a grade for the whole recipe.
Beverages remain unsupported without volume and sweetener inputs.

The OFF adapter uses the documented non-persisting reserved
[`PATCH /api/v3.6/product/test`](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/ref-v3/)
path, sends structured `nutrition.input_sets`, and accepts only the `2023` result.
The adapter returns its component points and caches successful exact-input
results for one hour. Upstream errors preserve computed nutrition and return
`dependency_error`. Calls have a ten-second timeout; product lookups are limited
to four concurrent requests. Live test-mode verification succeeded on 2026-10-07 and returned an algorithm-2023
grade and numeric score. Offline contract tests also include a published OFF
2023 golden response.
