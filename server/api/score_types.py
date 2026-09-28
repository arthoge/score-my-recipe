"""Types useful for green-score computation."""

import enum
from typing import Optional

from pydantic import BaseModel, Field


class AccountedWeights(enum.StrEnum):
    """Accounted weights for the ponderated sum.

    * scorable takes the ratio of each ingredient compared to the total weight of ingredients that have an EF score
    * total takes the ratio of each ingredient compared to the total weight of all ingredients, including unmatched ones
    """

    ONLY_SCORABLE = "scorable"
    ALL_WEIGHTS = "total"


class NotesMixin(BaseModel):
    """Mixin for models that can have notes."""

    notes: Optional[list[str]] = Field(
        default=None,
        description="Optional notes about computation specifics",
    )

    def add_note(self, note: str) -> None:
        """Add a note to the ingredient metrics."""
        if self.notes is None:
            self.notes = [note]
        else:
            self.notes.append(note)


class IngredientMetrics(NotesMixin):
    """Metrics gathered for a single ingredient during score computation

    Fields are filled incrementally by the score passes
    """

    id: str = Field(description="The frontend ingredient id")
    weight: float = Field(description="Weight in grams")
    ef_score: Optional[float] = Field(
        default=None,
        description="Per-kg EF score from Agribalyse (mPt/kg), None when the ingredient is missing",
    )
    labels_bonus: Optional[float] = Field(
        default=None,
        description="Bonus from ingredient labels",
    )
    epi_modifier: Optional[float] = Field(
        default=None,
        description="Modifier from ingredient origin agricultural system (EPI)",
    )
    distance_modifier: Optional[float] = Field(
        default=None,
        description="Modifier from ingredient origin distance to recipe country",
    )
    ratio: Optional[float] = Field(
        default=None,
        description="Share of the ingredient weight in the chosen denominator "
        "(scorable weight or total recipe weight)",
    )
    missing: bool = Field(
        default=False,
        description="True when the ingredient has no usable Agribalyse EF score",
    )


class RecipeMetrics(NotesMixin):
    """Metrics gathered for a recipe during green-score computation.

    Wraps the per-ingredient :class:`IngredientMetrics` computed by the score
    passes. The ``metrics`` list is filled by :func:`api.score.gather_ef_metrics`
    then mutated in place by the subsequent passes (ratios, labels, EPI and
    distance modifiers), so each :class:`IngredientMetrics` stays the single
    source of truth for its ingredient.
    """

    metrics: list[IngredientMetrics] = Field(
        default_factory=list,
        description="Per-ingredient metrics, one entry per recipe ingredient",
    )

    @property
    def ingredients_notes(self):
        """Return a dictionary of all notes from the ingredients metrics
        keyed by ingredient id.
        """
        return {
            metric.id: metric.notes
            for metric in self.metrics
            if metric.notes
        }