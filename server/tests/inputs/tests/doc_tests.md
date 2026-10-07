# Tests folder

This folder contains the deliverable components demonstrating that the
prototype works. It includes automated tests, two sample requests, and
an HTTP demonstration script.

## Contents

| File | Purpose |
| --- | --- |
| `test_api.py` | Five automated tests covering data, scanning, and validation. |
| `payloads/scan_recipe.json` | Valid sample recipe for the demonstration. |
| `payloads/invalid_recipe.json` | Invalid request: missing ingredients. |
| `run_tests.sh` | Runs all automated tests. |
| `run_http_demo.sh` | Temporarily starts the API and performs a real request. |

## Initial setup

From the prototype's root folder (the one containing `api.py`), run the
following commands once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the tests

With the virtual environment activated:

```bash
bash tests/run_tests.sh
```

Expected result:

```text
5 passed
```

## Starting the API

With the virtual environment activated:

```bash
python -m uvicorn api:app --reload
```

Open <http://127.0.0.1:8000/docs>. The endpoints will appear there, and you can
test `POST /scan-recipe` by pasting the content of
`payloads/scan_recipe.json`. Alternatively, the full demo is run with:

```bash
bash/run_http_demo.sh
```

It should first display `status: "ok"` and then a JSON object that recognizes `pera` and
`red wine`, leaves `mystery Powder` unresolved, and suggests
`es:vino-tinto-orgánico`.
