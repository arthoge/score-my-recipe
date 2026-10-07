# What the JSON files and API do

## Short version

This project does **not** store or copy a website. It is a local API: it receives a recipe that has already been parsed, looks up the JSON files in this folder, and returns JSON for the user interface to render in its table.

```text
Recipe text/URL → recipe parser → ingredient table → local API → JSON response → UI/PDF
```

This folder contains the data and API in the middle of that flow. It also contains a standalone visual demo in `frontend-demo/`. That demo is not the original application frontend; it exists to test the new button while the real client is integrated.

## JSON files

| File | Contents | Use |
| --- | --- | --- |
| `ingredients.full.json` | A reduced Open Food Facts taxonomy: ids, translated names, synonyms and parent/child links. | Recognizes names such as `pera`, `pear`, and `red wine`. |
| `labels.full.json` | 26 certification/label entries. | Powers `/labels/search`. |
| `make_it_better_catalog.json` | Explicit products, Nutri-Score, Green-Score, and allowed alternatives. | Powers Make it better. |
| `frontend-demo/` | Static demo (`index.html`, `app.js`, `styles.css`). | Lets someone see and test the button without the real frontend. |

A JSON file is structured text. An id such as `en:pear` is a stable key with translated names inside it; it does not mean the project stores a physical ingredient or a user's recipe.

## What `api.py` does

`api.py` creates the FastAPI server. At startup it loads the JSON data once, validates ingredient links, and builds lookup indexes that tolerate capitalization and accents.

| Route | Input | Result |
| --- | --- | --- |
| `GET /health` | None | Confirms loaded data. |
| `POST /scan-recipe` | Extracted ingredient names. | Returns recognized, unresolved, and taxonomy-backed items. |
| `GET /ingredients/{id}` | An id such as `en:pear`. | Returns an ingredient record. |
| `GET /labels/search` | Search text. | Returns matching labels. |
| `POST /make-it-better/check` | Products from the main table. | Returns the strongest Nutri-Score, Green-Score, or combined improvement. |
| `GET /demo/` | None. | Serves the visual demo. |

The original taxonomy is not a product-score catalogue. It cannot prove that a particular product has a better score. Product-level data and a declared criterion are required. The new comparison uses catalogued Nutri-Score and Green-Score values; it is informational, not medical advice or allergy checking.

## Run it

```bash
source .venv/bin/activate
python -m uvicorn api:app --reload
```

Open `http://127.0.0.1:8000/docs` to inspect the API or `http://127.0.0.1:8000/demo/` to see the button demo.
