# Nutrition and prepared-weight data sources

These sources support the recipe nutrition and prepared-weight features.
Their terms are separate from the application's AGPL-3.0 license.

## Ciqual 2025

ANSES, _Table de composition nutritionnelle des aliments Ciqual 2025_,
[DOI 10.57745/RDMHWY](https://doi.org/10.57745/RDMHWY).
The derived catalogs contain 3,484 food identities and eight nutrient fields,
with official food groups. Missing values, traces and quantified upper limits
are retained. License: [Open Licence 2.0](https://spdx.org/licenses/etalab-2.0.html).

Pinned source files:

- Identities: [`alim_2025_11_03.xml`, file 666252](https://entrepot.recherche.data.gouv.fr/api/access/datafile/666252),
  SHA-256 `e0b1de25b3039028205e9d54a96892e403e1b313c2efeb41180fabe132627478`.
- Nutrients: [workbook, file 666260](https://entrepot.recherche.data.gouv.fr/api/access/datafile/666260),
  SHA-256 `5555c572fa3735991298d832d0427788fa69a11b4fd20a5d580d58942369fbb0`.

From `server`, rebuild deliberately with network access:

```bash
uv run typer api/cli.py run fetch-ciqual
uv run typer api/cli.py run fetch-ciqual-nutrients
```

The fetchers verify source hashes. Inspect changes and run calculation tests
before updating bundled data. See the [resource README](../server/api/resources/README.md)
for composition selection and cooking counterparts.

## Prepared-weight estimates

A. Bognár (2002), _Tables on weight yield of food and retention factors of food
constituents for the calculation of nutrient composition of cooked foods (dishes)_,
[report](https://www.fao.org/uploads/media/bognar_bfe-r-02-03.pdf).

The catalog version is **bognar-2002-v1**. Four narrow profiles cover boiled
white long-grain/basmati rice, dried egg pasta, dried lentils and steamed peeled
potatoes. Individual table/page citations, factors and conditions are recorded in
[`preparation-yields-v1.json`](../server/api/resources/preparation-yields-v1.json).
These are weight-yield estimates, not a general nutrient-retention model.
Publication reuse terms need confirmation before wider redistribution.

## Open Food Facts and Nutri-Score

Product composition comes from Open Food Facts contributors and is live data,
not a pinned product snapshot. Attribution: **Open Food Facts contributors**.
The database is ODbL and individual database contents are DbCL; see
[OFF licensing documentation](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/tutorials/license-be-on-the-legal-side/).

The calculator requires an **algorithm-2023** response from OFF's reserved,
non-persisting `PATCH /api/v3.6/product/test` endpoint. Older algorithm responses
are rejected. Official method resources are published by
[Santé publique France](https://www.santepubliquefrance.fr/nutrition-et-activite-physique/nutri-score).

The unmodified English 2023 Nutri-Score illustrations and their source URLs are
listed in the [asset README](../frontend/src/lib/assets/nutri-score/README.md).
Keep the source attribution and confirm applicable official logo usage terms
before public release; source URLs do not grant trademark rights or certify the
application.
