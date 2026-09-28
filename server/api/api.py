"""HTTP API for recipes scoring.


Note: the business logic is in api/recipes.py,
this file should only handle the HTTP specific parts.
"""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import api.recipes as recipes
import api.exceptions as exceptions
import api.score as score
import api.types as types
import api.units as units

app = FastAPI(
    title="Score My Recipe",
    description="A tool to compute Green-Score of recipes.",
    version="0.1.0",
)


@app.exception_handler(types.AsyncRequestValidationError)
async def async_validation_exception_handler(
    request: Request, exc: types.AsyncRequestValidationError
) -> JSONResponse:
    """Convert async model validation errors into HTTP 422 responses.

    Async validators (e.g. the language/country code checks, run by
    :func:`api.types.async_validate_model`) raise ``pydantic.ValidationError``
    from within the endpoint. FastAPI only auto-converts its own
    ``RequestValidationError`` (raised while parsing the request) to 422, so
    without this handler the async ones would surface as a 500.
    """
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


# Allow anyone to call the API from their own apps
app.add_middleware(
    CORSMiddleware,
    # FastAPI doc related to allow_origin (to avoid CORS issues):
    # "It's also possible to declare the list as "*" (a "wildcard") to say that all are allowed.
    # But that will only allow certain types of communication, excluding everything that involves
    # credentials: Cookies, Authorization headers like those used with Bearer Tokens, etc.
    # So, for everything to work correctly, it's better to specify explicitly the allowed origins."
    # => Workaround: use allow_origin_regex
    # Source: https://github.com/tiangolo/fastapi/issues/133#issuecomment-646985050
    allow_origin_regex="https?://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {"message": "Score My Recipe API"}


@app.get("/v1/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/parse_text")
@types.async_validate_model
async def parse_text(request: types.RecipeParseRequest) -> types.RecipeParseResponse:
    """Parse a text and return a list of ingredients with quantities and eventual modifiers"""
    ingredients = await recipes.parse_text(request.text, request.lang)
    return types.RecipeParseResponse(ingredients=ingredients)


@app.get("/v1/origins", response_model_exclude_none=True)
@types.async_validate_model
async def get_origins(
    filter_query: Annotated[types.OriginsRequest, Query()], response: Response
) -> types.OriginsResponse:
    """Get the list of origins available in the database

    Note: as the list is not too big, we let clients handle suggestions to users
    """
    origins = await recipes.get_origins(filter_query.lang, filter_query.include_synonyms)
    response.headers["Cache-Control"] = "max-age=86400"
    return types.OriginsResponse(origins=origins)


@app.get("/v1/labels", response_model_exclude_none=True)
@types.async_validate_model
async def get_labels(
    filter_query: Annotated[types.LabelsRequest, Query()], response: Response
) -> types.LabelsResponse:
    """Get the list of labels relevant for green-score computation"""
    labels = await recipes.get_labels(filter_query.lang, filter_query.include_synonyms)
    response.headers["Cache-Control"] = "max-age=86400"
    return types.LabelsResponse(labels=labels)


@app.get("/v1/countries", response_model_exclude_none=True)
@types.async_validate_model
async def get_countries(
    filter_query: Annotated[types.CountriesRequest, Query()], response: Response
) -> types.CountriesResponse:
    """Get the list of countries relevant for green-score computation"""
    countries = await recipes.get_countries(filter_query.lang, filter_query.include_synonyms)
    response.headers["Cache-Control"] = "max-age=86400"
    return types.CountriesResponse(countries=countries)


@app.get("/v1/ingredients", response_model_exclude_none=True)
@types.async_validate_model
async def get_ingredients(
    filter_query: Annotated[types.IngredientsRequest, Query()], response: Response
) -> types.IngredientsResponse:
    """Get the list of ingredients relevant for green-score computation"""
    ingredients = await recipes.get_ingredients(filter_query.lang, filter_query.include_synonyms)
    response.headers["Cache-Control"] = "max-age=86400"
    return types.IngredientsResponse(ingredients=ingredients)


@app.get("/v1/units", response_model_exclude_none=True)
@types.async_validate_model
async def get_units(
    filter_query: Annotated[types.UnitsRequest, Query()], response: Response
) -> types.UnitsResponse:
    """Get the list of units available in the Open Food Facts units taxonomy

    Note: as the list is not too big, we let clients handle suggestions to users
    """
    unit_list = await units.get_units(filter_query.lang, filter_query.include_synonyms)
    response.headers["Cache-Control"] = "max-age=86400"
    return types.UnitsResponse(units=unit_list)


@app.get("/v1/suggest-scored-ingredient", response_model_exclude_none=True)
@types.async_validate_model
async def suggest_scored_ingredient(
    filter_query: Annotated[types.SuggestScoredIngredientRequest, Query()], response: Response
) -> types.SuggestScoredIngredientResponse:
    """Suggest scored ingredient alternatives for an ingredient with no Agribalyse match.

    Given a taxonomy id (typically one returned in ``missing_ingredient_ids``),
    walk down the ingredients taxonomy and return the descendants that resolve
    to an Agribalyse row, so the user can pick a more specific alternative.
    """
    ingredients = await recipes.suggest_scored_ingredient(
        filter_query.lang, filter_query.include_synonyms, filter_query.taxonomy_id
    )
    response.headers["Cache-Control"] = "max-age=86400"
    return types.SuggestScoredIngredientResponse(ingredients=ingredients)


@app.post("/v1/green-score")
@types.async_validate_model
async def green_score(request: types.GreenScoreRequest) -> types.GreenScoreResponse:
    """Compute the green-score of a recipe given as a list of ingredients."""
    return await score.compute_green_score(
        request.ingredients,
        accounted_weights=request.accounted_weights,
        country=request.country,
    )


@app.post("/v1/recompute-quantity")
@types.async_validate_model
async def recompute_quantity(
    request: types.RecomputeQuantityRequest,
) -> types.RecomputeQuantityResponse:
    """Recompute the quantity in grams after the user edited an ingredient's value/unit.

    This is useful to let user change the value of a recipe item in a natural fashion
    (eg. change 1 egg to 3 eggs)
    while keeping the equivalent "g" conversion for green-score computation.

    A best effort is done to also allow changing the unit,
    but currently, only new units that can be converted to grams are supported.

    Units may be given as a taxonomy id, a localized unit name (resolved using
    ``lang``) or the ``item`` sentinel for countable ingredients.
    """
    try:
        quantity_g, value, unit = await units.recompute_quantity(
            request.quantity_g,
            request.old_value,
            request.old_unit,
            request.new_value,
            request.new_unit,
            request.lang,
        )
    except exceptions.UnknownUnitError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except exceptions.UnitConversionNotSupportedError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return types.RecomputeQuantityResponse(quantity_g=quantity_g, value=value, unit=unit)
