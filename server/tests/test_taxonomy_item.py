"""Tests for the ``TaxonomyItem`` model and its id / is_in_taxonomy validator.

A ``TaxonomyItem`` whose ``id`` is ``None`` is a free-text entry: it is, by
definition, not resolved to a taxonomy node, so it must not be flagged
``is_in_taxonomy=True``. This is enforced by a model validator.
"""

import pytest
from pydantic_core import ValidationError

from api import types


def test_free_text_entry_is_valid_when_not_in_taxonomy():
    """A null id with is_in_taxonomy=False (a free-text entry) is accepted."""
    item = types.TaxonomyItem(id=None, label="custom", is_in_taxonomy=False)
    assert item.id is None
    assert item.is_in_taxonomy is False


def test_taxonomy_entry_is_valid_when_in_taxonomy():
    """A real taxonomy id with is_in_taxonomy=True is accepted."""
    item = types.TaxonomyItem(id="en:apple", label="Apple", is_in_taxonomy=True)
    assert item.id == "en:apple"


def test_id_present_but_not_in_taxonomy_is_valid():
    """An id may be present while is_in_taxonomy is false (resolved id, custom flag)."""
    item = types.TaxonomyItem(id="en:apple", label="Apple", is_in_taxonomy=False)
    assert item.is_in_taxonomy is False


def test_null_id_with_in_taxonomy_is_rejected():
    """A null id flagged as in-taxonomy violates the consistency rule."""
    with pytest.raises(ValidationError) as exc_info:
        types.TaxonomyItem(id=None, label="custom", is_in_taxonomy=True)
    assert "is_in_taxonomy" in str(exc_info.value)


def test_green_score_request_rejects_inconsistent_codified_ingredient():
    """A request body whose codified ingredient has a null id but isInTaxonomy=true
    is rejected at parse time (camelCase payload, as sent by the frontend)."""
    payload = {
        "ingredients": [
            {
                "id": "i1",
                "name": "custom",
                "weight": 100,
                "codifiedIngredient": {"id": None, "label": "custom", "isInTaxonomy": True},
                "labels": [],
                "isFreshPlant": False,
                "isInSeason": False,
                "origin": None,
            }
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        types.GreenScoreRequest.model_validate(payload)
    assert "is_in_taxonomy" in str(exc_info.value)


def test_green_score_request_accepts_consistent_free_text_codified_ingredient():
    """A request body whose codified ingredient is a free-text entry (null id,
    isInTaxonomy=false) is accepted."""
    payload = {
        "ingredients": [
            {
                "id": "i1",
                "name": "custom",
                "weight": 100,
                "codifiedIngredient": {"id": None, "label": "custom", "isInTaxonomy": False},
                "labels": [],
                "isFreshPlant": False,
                "isInSeason": False,
                "origin": None,
            }
        ]
    }
    request = types.GreenScoreRequest.model_validate(payload)
    assert request.ingredients[0].codified_ingredient.id is None
    assert request.ingredients[0].codified_ingredient.is_in_taxonomy is False
