# CIQUAL food identities

`ciqual-foods-2025.json` contains the 3,484 food codes and official French/English
names from ANSES's CIQUAL 2025 food list. It contains food identities only;
nutrient composition and Nutri-Score calculation remain separate work.

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
