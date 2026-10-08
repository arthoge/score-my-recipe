"""Canonical recipe inputs and independent score calculations shared by API features."""

import asyncio
import logging
from pydantic import ConfigDict, Field, model_validator
from api import nutrition, score, types

logger = logging.getLogger(__name__)


class ExportIngredient(nutrition.NutritionIngredient):
    """One canonical ingredient input for both score calculations and the printed list."""

    codified_ingredient: types.TaxonomyItem | None = None
    agribalyse_code: str | None = None
    labels: list[types.TaxonomyItem] = Field(default_factory=list)
    origin: types.TaxonomyItem | None = None
    is_fresh_plant: bool = False
    is_in_season: bool = False


class ExportRecipe(nutrition.NutritionRequest):
    """Recipe inputs only; browser-supplied scores are rejected."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    ingredients: list[ExportIngredient] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ingredients(self):
        """Keep exclusion counts and reference matching unambiguous."""
        if len({row.id for row in self.ingredients}) != len(self.ingredients):
            raise ValueError("Ingredient IDs must be unique within each recipe")
        return self


async def calculate_report(recipe: ExportRecipe):
    """Run the existing score algorithms independently, preserving available results."""
    green_inputs = [
        types.RecipeIngredientInput(
            id=row.id,
            name=row.name,
            weight=row.quantity_g or 0,
            codified_ingredient=row.codified_ingredient
            or types.TaxonomyItem(id=row.name, label=row.name, is_in_taxonomy=False),
            agribalyse_code=row.agribalyse_code,
            labels=row.labels,
            origin=row.origin,
            is_fresh_plant=row.is_fresh_plant,
            is_in_season=row.is_in_season,
        )
        for row in recipe.ingredients
    ]
    results = await asyncio.gather(
        score.compute_green_score(green_inputs, country=recipe.country),
        nutrition.analyze(
            nutrition.NutritionRequest(
                ingredients=recipe.ingredients, portions=recipe.portions, category=recipe.category
            )
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, Exception):
            raise result
        if isinstance(result, Exception):
            logger.warning("Recipe calculation unavailable: %s", result)
    return recipe, *(None if isinstance(result, Exception) else result for result in results)
