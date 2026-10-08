# “Make it better” implementation

## Outcome

The previous mozzarella-button version was removed. The new feature checks products submitted by the main window, finds an improvement in **Nutri-Score**, **Green-Score**, or both from a local database, and opens a modal so the user can decide each change.

```text
Main product table → Make it better → POST /make-it-better/check
→ modal with original and suggested bowls → Yes / No
→ Switch ingredient (only after Yes) or Next (after No) → next step
```

There is no automatic replacement. **Yes** only exposes `Switch ingredient`; the table row changes only when that second button is clicked. **No** keeps the original and advances to the next suggestion.

## Changed folders and files

| Path | Purpose |
| --- | --- |
| `api.py` | Backend: loads the catalog, selects the strongest improvement, and exposes the check route. It also serves the visual demo. |
| `make_it_better_catalog.json` | Local product database: both scores and allowed alternatives, including the chocolate-yogurt example. |
| `frontend-demo/index.html` | Test main window and modal structure with two bowls. |
| `frontend-demo/app.js` | Sends the list, renders scores, manages Yes/No, and changes an item only after `Switch ingredient`. |
| `frontend-demo/styles.css` | Table, modal, and bowl styling. |
| `tests/test_api.py` | Checks strongest-improvement selection and products without an improvement. |

## Backend

`POST /make-it-better/check` receives table products:

```json
{
  "ingredients": ["chocolate yogurt", "tomato", "flour"],
  "language": "es"
}
```

For every known product, it compares the alternatives declared in `make_it_better_catalog.json`. It maps A=5, B=4, C=3, D=2, E=1; adds the Nutri-Score and Green-Score gains; and returns **one** option—the highest combined gain. A single improved score returns one improvement; two improved scores return both.

The example turns chocolate yogurt (D/D) into organic plain yogurt (A/A). Unknown products are returned in `no_improvement`; nothing is invented.

## Frontend and modal

The demo is served at `GET /demo/`. It provides the main table, **Make it better**, and **Next**. When suggestions exist, it opens a modal containing the original bowl, suggested bowl, both scores, the exact score changes, and **Yes** / **No, keep original**.

After **Yes**, `Switch ingredient` appears. Clicking it updates the matching table row and advances. **No** leaves the row unchanged and advances. The modal closes after the final suggestion.

## How to test it

From `/home/elerazo/score-my-recipe/server/tests/inputs`:

```bash
source .venv/bin/activate
python -m uvicorn api:app --reload
```

Open `http://127.0.0.1:8000/demo/`.

1. The initial list contains `yogur de chocolate`, tomato, and flour.
2. Click **Make it better**.
3. Confirm that the modal shows both bowls and the two D → A improvements.
4. Click **No, mantener original**: the yogurt remains unchanged.
5. Repeat, click **Sí**, then **Switch ingredient**: the first row changes to `Yogur natural ecológico`.
6. Enter an uncatalogued product and try again: no unsupported suggestion appears.

Run backend checks with:

```bash
.venv/bin/python -m pytest -q tests
```

## Production data requirement

The present catalog is a local integration example, not a live product feed. Before production, populate `make_it_better_catalog.json` with reliable product ids and current Nutri-Score/Green-Score values, plus an update source and cadence.
