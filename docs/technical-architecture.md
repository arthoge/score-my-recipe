# Architecture notes

The project's initial goal is to compute the Green-Score for recipes. It also computes Nutri-Score 2023 and recipe nutrition. NOVA is not implemented.

## A frontend and an API

We want to provide a frontend for the general public to use the tool.
We also want to provide an API so consumers can integrate score computations into their own tools.
To encourage broad adoption, the API should provide everything consumers need for straightforward integration, regardless of the technology they use.

This means **Any business logic must go to the API**.
That is any logic around recipe parsing, ingredients handling, completion, warnings, etc. and of course the score computation.
The frontend should only care about presentation and interaction logic.

## Some best practices

Of course we follow FastAPI and Svelte best practice in general.

Use Pydantic models to define API request and response schemas, especially response bodies.
This keeps the generated OpenAPI specification and documentation accurate,
allows us to auto-generate JavaScript bindings,
and helps potential integrators consume the API.

Keep Svelte files small and focused on one main responsibility.
- Extract small Svelte components as needed.
- Split logic into `frontend/src/lib/` (`types/`, `ui/`, and `api/`).
