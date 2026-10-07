# Score my Recipe

A tool to compute Green Score and Nutri-Score for recipes.

* Green-Score is an assesment of the environmental impact of food. For the methodology, please see https://docs.score-environnemental.com/ and most notably the Recipe methodology: https://docs.score-environnemental.com/methodologie-recette/fonctionnement-general-recette

## Recipe scoring

Paste recipes on `/add`, then review ingredients and references on `/score`.
Green Score and Nutri-Score update automatically when quantities or references
change; additional ingredient rows are added manually.

Nutri-Score uses Open Food Facts product composition or ANSES Ciqual 2025 and
Open Food Facts' 2023 calculator. Prepared ingredient weights use documented
cooking yields where available, otherwise entered quantities. Suggestions can
be edited; input changes can recalculate them. The recipe total is read-only.
Portions affect nutrition per portion, not the per-100-g grade.

Review automatic matches and excluded ingredients: partial scores describe the
included subset. See [scoring limitations](docs/scoring-limitations.md) and
[nutrition data sources](docs/data-sources.md).

## Printable recipe reports

On `/score`, use **Export recipes** to select recipes and download a compact A4 PDF.
`POST /v1/recipes/export` accepts recipe inputs and recalculates both scores on
the backend; it does not accept browser-supplied scores. Reports include ingredient
quantities, available scores and exclusion summaries, nutrition, additives,
allergens and a data-quality disclaimer. Missing data remains unavailable.

ReportLab and svglib are installed with the backend's normal `uv sync` command.
Images and fonts are bundled in `server/api/resources/pdf`, with attribution there.
Reports currently use English headings and support up to 20 recipes per request,
with 100 ingredients per recipe. Printing is enabled and PDF editing permissions
are restricted; these permissions do not guarantee protection against alterations.

## Getting started

* See [docs/dev-quick-start.md](docs/dev-quick-start.md) for instructions on how to run the backend from the `server/` folder.


## Known issues
* Please coordinate with @alexgarel (eventually on our [slack](https://slack.openfoodfacts.org)) and see [github project to see priorities](https://github.com/orgs/openfoodfacts/projects/167/)
* Feel free to report and document any issues we may have missed.

Read [Architecture notes](docs/technical-architecture.md)

## Sponsors

This project was made possible thanks to the Appel à commun pour la transition écologique run by [ADEME](https://www.ademe.fr/) (french state environmental agency).
