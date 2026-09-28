import functools
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from pydantic_core import ValidationError
from pydantic_async_validation import AsyncValidationModelMixin, async_field_validator

import api.exceptions as api_exceptions
import api.score_types as score_types


# Sentinel value used as a "unit" when the quantity refers to countable items
# (e.g. "1 egg", "2 broccoli") rather than a measurable mass or volume.
# It is deliberately distinct from any OFF taxonomy id (``en:...`` / ``xx:...``)
# so it cannot be confused with a real unit.
ITEM_UNIT = "item"


def async_validate_model(fn):
    """Decorator to run async validation on a Pydantic model before calling the function.

    The decorated function must have the Pydantic model as first argument
    and will be validated before
    the function is called. If validation fails, a ``ValidationError`` is raised.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        for arg in list(args) + list(kwargs.values()):
            if isinstance(arg, AsyncValidationModelMixin):
                try:
                    await arg.model_async_validate()
                except ValidationError as e:
                    # encapsulate so that we can use a specific exception handler
                    raise api_exceptions.AsyncRequestValidationError(e.errors()) from e
        return await fn(*args, **kwargs)

    return wrapper


class OFFIngredient(BaseModel):
    """Ingredient model for Open Food Facts API"""

    # TODO convert str to bool and is_in_taxonomy to bool
    id: str
    text: str
    quantity: Optional[str] = None
    quantity_ml: Optional[float] = None
    quantity_g: Optional[float] = None
    ecobalyse_code: Optional[str] = None
    ciqual_food_code: Optional[str] = None
    is_in_taxonomy: Optional[int] = None
    origins: Optional[str] = None  
    labels: Optional[str] = None 

    @field_validator("quantity", mode="before")
    def transform_id_to_str(cls, value) -> str:
        """ensure that the quantity is always a string,
        even if it is a number in the input"""
        return str(value)


class RecipeIngredient(BaseModel):
    """Ingredient model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "taxonomy_id": "en:apple",
                    "is_in_taxonomy": True,
                    "codified_ingredient": "apple",
                    "quantity_g": 150.0,
                    "origins": "en:france",
                    "labels": ["en:organic"],
                    "quantity_value": 0.15,
                    "quantity_unit": "kg",
                }
            ]
        }
    )

    taxonomy_id: Annotated[Optional[str], Field(description="Taxonomy id of the ingredient")] = None
    is_in_taxonomy: Annotated[bool, Field(description="Whether the ingredient is in the taxonomy")]
    codified_ingredient: Annotated[str, Field(description="Codified ingredient name")]
    quantity_g: Annotated[Optional[float], Field(description="Quantity in grams")] = None
    origins: Annotated[Optional[str], Field(description="Origins of the ingredient")] = None
    labels: Annotated[Optional[list[str]], Field(description="Labels of the ingredient")] = None
    quantity_value: Annotated[
        Optional[float], Field(description="Numeric value of the quantity")
    ] = None
    quantity_unit: Annotated[Optional[str], Field(description="Unit of the quantity")] = None
    notes: Annotated[Optional[list[str]], Field(description="Notes about the ingredient")] = None


class TaxonomyItem(BaseModel):
    """A taxonomy reference with an id and a localized label.

    Mirrors the frontend `TaxonomyItem` (used for codified ingredients, labels
    and origins).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "en:apple", "label": "Apple", "synonyms": ["apples", "pommes"]}]
        }
    )

    id: Annotated[str, Field(description="Taxonomy id of the item")]
    label: Annotated[str, Field(description="Name of the item")]
    synonyms: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="Synonyms in the requested language. "
            "Only present in the response when include_synonyms is true.",
        ),
    ]


class Origin(TaxonomyItem):
    """Origin model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "en:france", "label": "France", "synonyms": ["french"]}]
        }
    )


class RecipeParseResponse(BaseModel):
    """Response model for parse_text endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ingredients": [
                        {
                            "taxonomy_id": "en:apple",
                            "is_in_taxonomy": True,
                            "codified_ingredient": "apple",
                            "quantity_g": 150.0,
                        },
                        {
                            "taxonomy_id": "en:wheat-flour",
                            "is_in_taxonomy": True,
                            "codified_ingredient": "wheat flour",
                            "quantity_g": 200.0,
                        },
                    ]
                }
            ]
        }
    )

    ingredients: list[RecipeIngredient]


class LangRequest(AsyncValidationModelMixin, BaseModel):
    """Request model for parse_text endpoint"""

    model_config = ConfigDict(json_schema_extra={"examples": [{"lang": "en"}]})

    lang: Annotated[str, Field(description="Language for the request (2 or 5 letter code)")]

    @async_field_validator("lang")
    async def check_language_code(self, value: str) -> str:
        """Check if the language code is valid (exists in the OFF languages taxonomy)"""
        import api.checks as checks

        if not await checks.check_language_code(value):
            raise ValueError(f"Language code {value} is not supported")
        return value


class TaxonomyRequest(LangRequest):
    """Base request model for taxonomy endpoints (origins, labels, ingredients).

    Adds the option to request synonyms alongside the canonical label.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": False}]}
    )

    include_synonyms: Annotated[
        bool,
        Field(
            default=False,
            description="If true, include the synonyms of each item in the response.",
        ),
    ]


class OriginsRequest(TaxonomyRequest):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": True}]}
    )
    pass  # No additional fields for now, but we keep the class for future extensions


class RecipeParseRequest(LangRequest):
    """Request model for parse_text endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"lang": "en", "text": "200g of apple, 1 cup of wheat flour"}]
        }
    )

    text: str


class OriginsResponse(BaseModel):
    """Response model for get_origins endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "origins": [
                        {"id": "en:france", "label": "France", "synonyms": ["french"]},
                        {"id": "en:spain", "label": "Spain", "synonyms": ["spanish"]},
                    ]
                }
            ]
        }
    )

    origins: list[Origin]


class Label(TaxonomyItem):
    """Label model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "en:eu-organic", "label": "EU Organic", "synonyms": ["bio"]}]
        }
    )


class LabelsRequest(TaxonomyRequest):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": False}]}
    )
    pass


class LabelsResponse(BaseModel):
    """Response model for get_labels endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "labels": [
                        {"id": "en:eu-organic", "label": "EU Organic"},
                        {"id": "en:fair-trade", "label": "Fair Trade"},
                    ]
                }
            ]
        }
    )

    labels: list[Label]


class Country(TaxonomyItem):
    """Country model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "en:france", "label": "France", "synonyms": ["french"]}]
        }
    )

    country_code: Annotated[
        Optional[str],
        Field(
            default=None,
            description="ISO 3166-1 alpha-2 country code",
        ),
    ]


class CountriesRequest(TaxonomyRequest):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": False}]}
    )
    pass


class CountriesResponse(BaseModel):
    """Response model for get_countries endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "countries": [
                        {"id": "en:france", "label": "France"},
                        {"id": "en:spain", "label": "Spain"},
                    ]
                }
            ]
        }
    )

    countries: list[Country]


class Ingredient(TaxonomyItem):
    """Ingredient model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "en:apple", "label": "Apple", "synonyms": ["apples"]}]
        }
    )


class IngredientsRequest(TaxonomyRequest):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": True}]}
    )
    pass


class IngredientsResponse(BaseModel):
    """Response model for get_ingredients endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ingredients": [
                        {"id": "en:apple", "label": "Apple"},
                        {"id": "en:wheat-flour", "label": "Wheat flour"},
                    ]
                }
            ]
        }
    )

    ingredients: list[Ingredient]


class Unit(TaxonomyItem):
    """Unit model for Score My Recipe API"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": "en:gram", "label": "gram", "standard_unit": "g", "synonyms": ["g", "grams"]}
            ]
        }
    )

    standard_unit: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Standard unit the unit converts to (e.g. 'g', 'ml', 'kJ'). "
            "Omitted when the taxonomy does not define one for this unit.",
        ),
    ]


class UnitsRequest(TaxonomyRequest):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"lang": "en", "include_synonyms": False}]}
    )
    pass


class UnitsResponse(BaseModel):
    """Response model for get_units endpoint"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "units": [
                        {"id": "en:gram", "label": "gram", "standard_unit": "g"},
                        {"id": "en:cup", "label": "cup", "standard_unit": "ml"},
                    ]
                }
            ]
        }
    )

    units: list[Unit]


class ScoredIngredient(Ingredient):
    """An ingredient alternative with its matching Agribalyse row code.

    Mirrors the ``Ingredient`` structure (so it can be presented to the user just
    like the ``get_ingredients`` results) and adds the Agribalyse row code that
    the suggestion resolves to. Exposes camelCase aliases (matching the frontend
    convention) for multi-word fields.
    """

    model_config = ConfigDict()

    agribalyse_code: Annotated[
        str,
        Field(description="The Agribalyse row code (row identity) matching this ingredient"),
    ]

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {"id": "en:apple", "label": "Apple", "agribalyse_code": "10001"},
                {"id": "en:wheat-flour", "label": "Wheat flour", "agribalyseCode": "10602"},
            ]
        },
    )


class SuggestScoredIngredientRequest(TaxonomyRequest):
    """Request model for the suggest-scored-ingredient endpoint."""

    taxonomy_id: Annotated[
        str,
        Field(description="Taxonomy id of the ingredient to find alternatives for"),
    ]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"lang": "en", "include_synonyms": False, "taxonomy_id": "en:meat"}]
        }
    )


class SuggestScoredIngredientResponse(BaseModel):
    """Response model for the suggest-scored-ingredient endpoint."""

    ingredients: list[ScoredIngredient]


# --- Green-score computation -------------------------------------------------
#
# The following models mirror the frontend ingredient structures
# (see `frontend/src/lib/types/ingredient.ts`). They use camelCase aliases
# so the JSON accepted by the API matches what the SvelteKit frontend sends.


class CamelModel(BaseModel):
    """Base model exposing camelCase aliases (matching the frontend) in the OpenAPI schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TaxonomyItem(CamelModel):
    """A taxonomy reference with an id and a localized label.

    Mirrors the frontend `TaxonomyItem` (used for codified ingredients, labels
    and origins).
    """

    # json_schema_extra is merged with the inherited CamelModel config
    # (alias_generator + populate_by_name are preserved).
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": "en:apple", "label": "Apple", "isInTaxonomy": True}]}
    )

    id: Annotated[str, Field(description="Taxonomy identifier")]
    label: Annotated[str, Field(description="Display label in the current language")]
    is_in_taxonomy: Annotated[
        bool, Field(description="Whether the item comes from the taxonomy (true) or is custom")
    ]


class RecipeIngredientInput(CamelModel):
    """A single ingredient of a recipe"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "i1",
                    "name": "apple",
                    "weight": 150,
                    "codifiedIngredient": {
                        "id": "en:apple",
                        "label": "Apple",
                        "isInTaxonomy": True,
                    },
                    "labels": [
                        {
                            "id": "en:eu-organic",
                            "label": "EU Organic",
                            "isInTaxonomy": True,
                        }
                    ],
                    "isInSeason": False,
                    "origin": {
                        "id": "en:france",
                        "label": "France",
                        "isInTaxonomy": True,
                    },
                }
            ]
        }
    )

    # TODO: decide if we keep id and name
    id: Annotated[str, Field(description="Unique identifier for the ingredient")]
    name: Annotated[str, Field(description="Display name of the ingredient")]
    weight: Annotated[float, Field(description="Weight in grams")]
    codified_ingredient: Annotated[
        TaxonomyItem,
        Field(description="Codified ingredient"),
    ]
    labels: Annotated[
        list[TaxonomyItem], Field(description="Labels / certifications (organic, fair-trade...)")
    ] = []
    is_fresh_plant: Annotated[
        bool, Field(description="Whether the ingredient is a fresh plant")
    ] = False
    is_in_season: Annotated[bool, Field(description="Whether the ingredient is in season")] = False
    origin: Annotated[
        Optional[TaxonomyItem], Field(description="Origin country/region, null if unspecified")
    ] = None


RecipeInput = list[RecipeIngredientInput]


class GreenScoreRequest(CamelModel):
    """Request body for the green-score computation endpoint.

    It is a thin wrapper around a list of ingredients
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "country": "FR",
                    "accountedWeights": "scorable",
                    "ingredients": [
                        {
                            "id": "i1",
                            "name": "apple",
                            "weight": 150,
                            "codifiedIngredient": {
                                "id": "en:apple",
                                "label": "Apple",
                                "isInTaxonomy": True,
                            },
                            "labels": [],
                            "isInSeason": False,
                            "origin": None,
                        },
                        {
                            "id": "i2",
                            "name": "wheat flour",
                            "weight": 200,
                            "codifiedIngredient": {
                                "id": "en:wheat-flour",
                                "label": "Wheat flour",
                                "isInTaxonomy": True,
                            },
                            "labels": [],
                            "isInSeason": False,
                            "origin": None,
                        },
                    ],
                }
            ]
        }
    )

    ingredients: Annotated[RecipeInput, Field(description="The ingredients of the recipe")]

    country: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Country code (ISO 3166-1 alpha-2) to compute the distance modifier for the recipe."
            "If not provided, the distance will always be world",
        ),
    ] = None

    accounted_weights: Annotated[
        score_types.AccountedWeights,
        Field(
            default=score_types.AccountedWeights.ONLY_SCORABLE,
            description=score_types.AccountedWeights.__doc__,
        ),
    ] = score_types.AccountedWeights.ONLY_SCORABLE

    @field_validator("country", mode="before")
    def upper_country_code(cls, value: Optional[str]) -> Optional[str]:
        """Ensure the country code is uppercase (ISO 3166-1 alpha-2)

        And is a 2-letter code if provided. If not, return None.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Country code must be a string, got {type(value)}")
        if len(value) != 2:
            raise ValueError(f"Country code must be 2 letters, got {value}")
        return value.upper()

    @async_field_validator("country")
    async def check_country_code(self, value: str) -> str:
        """Check if the country code is valid (exists in the OFF countries taxonomy)"""
        import api.checks as checks

        if not await checks.check_country_code(value):
            raise ValueError(f"Country code {value} is not supported")
        return value


class IngredientAgribalyse(CamelModel):
    """Per-ingredient result of the green-score computation.

    For now only the Agribalyse lookup result is returned; the actual score
    fields will be added later.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "i1",
                    "name": "apple",
                    "matchedCode": "10001",
                    "codeSource": "agribalyse_food_code",
                    "agribalyse": {
                        "code": "10001",
                        "ciqual_code": "20001",
                        "name_fr": "Apple",
                        "score": 0.3,
                    },
                }
            ]
        }
    )

    id: Annotated[str, Field(description="The frontend ingredient id")]
    name: Annotated[str, Field(description="The ingredient display name")]
    matched_code: Annotated[
        Optional[str], Field(description="The code used to find the Agribalyse row, null if none")
    ] = None
    code_source: Annotated[
        Optional[str],
        Field(description="The taxonomy property that yielded the code, null if none"),
    ] = None
    agribalyse: Annotated[
        Optional[dict[str, Any]],
        Field(description="The matching Agribalyse row as a dict, null if not found"),
    ] = None


class GreenScoreResponse(CamelModel):
    """Response model for the green-score computation endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "numericScore": 76.38,
                    "letterGrade": "A",
                    "missingIngredientIds": [],
                }
            ]
        }
    )

    global_ef_score: Annotated[
        Optional[float],
        Field(
            description="The computed global EF score of the recipe, null if no ingredients have a score"
        ),
    ] = None
    labels_bonus: Annotated[
        Optional[float],
        Field(
            description="The bonus from ingredient labels, null if no ingredients have a score, 0 if no labels"
        ),
    ] = None
    epi_modifier: Annotated[
        Optional[float],
        Field(
            description="The modifier from ingredient origin agricultural system (EPI), null if no ingredients have a score"
        ),
    ] = None
    distances_modifier: Annotated[
        Optional[float],
        Field(
            description="The modifier from ingredient origin distance, null if no ingredients have a score"
        ),
    ] = None
    seasonality_modifier: Annotated[
        Optional[float],
        Field(
            description="The modifier from ingredient seasonality, null if no ingredients have a score"
        ),
    ] = None
    numeric_score: Annotated[
        Optional[float],
        Field(
            description="The computed green-score of the recipe, null if no ingredients have a score"
        ),
    ] = None
    letter_grade: Annotated[
        Optional[str],
        Field(
            description="The letter grade corresponding to the numeric score, null if no ingredients have a score"
        ),
    ] = None
    missing_ingredient_ids: Annotated[
        list[str],
        Field(
            description="List of ingredient ids that were missing from the Agribalyse computation"
        ),
    ] = []
    notes: Annotated[
        Optional[list[str]],
        Field(
            description="Notes about the recipe-level score computation "
            "(e.g. seasonality), null when no ingredients have a score"
        ),
    ] = None
    ingredients_notes: Annotated[
        Optional[dict[str, list[str]]],
        Field(
            description="Per-ingredient notes keyed by ingredient id, "
            "only entries with at least one note are included, "
            "null if no ingredients have a score"
        ),
    ] = None


class RecomputeQuantityRequest(LangRequest, CamelModel):
    """Request body for the ``POST /v1/recompute-quantity`` endpoint.

    Each unit (``old_unit`` / ``new_unit``) may be given either as a unit id
    from the OFF units taxonomy (e.g. ``xx:kg``), as a localized unit name
    resolvable through the units taxonomy (e.g. ``"kg"``, ``"tasse"``), or as
    the ``item`` sentinel for countable ingredients (e.g. "1 egg").
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "lang": "en",
                    "quantity_g": 2000,
                    "old_value": 2000,
                    "old_unit": "g",
                    "new_value": 2,
                    "new_unit": "kg",
                }
            ]
        }
    )

    quantity_g: Annotated[float, Field(ge=0, description="Previous quantity in grams")]
    old_value: Annotated[float, Field(ge=0, description="Previous numeric value of the quantity")]
    old_unit: Annotated[
        str, Field(description=f"Previous unit (unit name, taxonomy id or '{ITEM_UNIT}')")
    ]
    new_value: Annotated[float, Field(ge=0, description="New numeric value of the quantity")]
    new_unit: Annotated[
        str, Field(description=f"New unit (unit name, taxonomy id or '{ITEM_UNIT}')")
    ]
    # lang: Annotated[
    #     str,
    #     Field(
    #         description="Language code (2 or 5 letters) "
    #         "used to resolve unit names to their taxonomy id."
    #     ),
    # ]


class RecomputeQuantityResponse(CamelModel):
    """Response model for the ``POST /v1/recompute-quantity`` endpoint.

    The ``unit`` field echoes the ``new_unit`` sent in the request (it may be a
    unit name, a taxonomy id or ``{ITEM_UNIT}``).
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"quantityG": 2000, "value": 2, "unit": "kg"}]}
    )

    quantity_g: Annotated[float, Field(description="New quantity in grams")]
    value: Annotated[float, Field(description="New numeric value of the quantity")]
    unit: Annotated[
        str,
        Field(
            description="New unit, echoed from the request "
            f"(unit name, taxonomy id or '{ITEM_UNIT}')"
        ),
    ]
