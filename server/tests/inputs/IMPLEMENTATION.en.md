# Local implementation — Score My Recipe

## Outcome

This folder now contains a working API for the Open Food Facts hackathon
prototype. It accepts recipe ingredients, matches them against the local
taxonomy, preserves items it cannot identify, and returns alternatives only
when the included data supports them.

No files outside `server/tests/inputs` were changed.

## What changed

- `ingredients.full.json` was repaired. It is a 20-ingredient reduced fixture
  whose `children` arrays still referenced 152 absent identifiers. Only those
  broken references were removed; every remaining `parents` and `children`
  reference resolves inside the JSON.
- `api.py` adds a local FastAPI API. At startup it validates both JSON files,
  reporting the exact source ingredient and reference if a broken relationship
  is added later.
- Matching is case-, accent-, and translation-tolerant. For example, `pera`,
  `pear`, and `PÉRA` can match a local ingredient when it is present in the
  fixture's names or synonyms.
- A deliberately conservative taxonomy-backed suggestion was added: `red
  wine` can be replaced with `organic red wine`, because both nodes exist in
  the local taxonomy. The response explicitly says this is a certification
  hint, not a verified environmental score for a specific product.
- Local Open Food Facts labels can be searched through the API.
- `test_api.py` and `requirements.txt` provide repeatable installation and
  verification.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Confirms that both JSON files loaded and validated. |
| `POST /scan-recipe` | Scans a recipe ingredient list. |
| `GET /ingredients/{id}` | Returns a canonical ingredient, e.g. `en:pear`. |
| `GET /labels/search?query=organic` | Searches local certification labels. |
| `POST /make-it-better/check` | Selects the strongest catalogued Nutri-Score/Green-Score improvement. |
| `GET /docs` | FastAPI's interactive interface. |

## How to test it, step by step

From this folder, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests
uvicorn api:app --reload
```

In a second terminal, with the virtual environment active, run:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/scan-recipe \
  -H 'Content-Type: application/json' \
  -d '{"ingredients":["pera","red wine","mystery powder"],"language":"es"}'
curl 'http://127.0.0.1:8000/labels/search?query=organic&language=es'
```

You can also open `http://127.0.0.1:8000/docs` and submit the same request
using **Try it out**.

## Expected output

- `GET /health` returns `status: "ok"`, `ingredients: 20`, `labels: 26`, and `improvement_products: 3`.
- The test command ends with `6 passed`.
- The scan resolves `pera` as `en:pear` and `red wine` as `en:red-wine`.
- `mystery powder` appears in `unresolved_ingredients`; the API never claims
  to recognize an unknown input.
- `recommendations` contains `en:organic-red-wine` for `en:red-wine`, and the
  `notice` field makes clear that this is not a validated eco-score.

## Important demo limitation

The two JSON files are taxonomies and certifications, not a product catalogue
with environmental footprints. The API can therefore identify ingredients and
show a certified option only where the local data justifies it. Claiming that
an alternative is environmentally *better* requires product-level and/or
Agribalyse data and comparison of a defined metric. It is more credible to
state this limitation to hackathon judges than to make an unsupported claim.
