from unittest.mock import patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openfoodfacts import taxonomy as off_taxonomy

from api.api import app
from api import recipes
from api import types

from tests.helpers import patch_language_check


client = TestClient(app)


LABELS_JSON_PATH = Path(__file__).parent / "inputs" / "labels.full.json"


@pytest.fixture
def mock_labels_taxonomy():
    """Load the labels taxonomy from the test input file via get_taxonomy"""
    labels_taxonomy = off_taxonomy.Taxonomy.from_path(LABELS_JSON_PATH)
    with (
        patch("openfoodfacts.taxonomy.get_taxonomy", return_value=labels_taxonomy),
        patch_language_check(),
    ):
        yield


def label_list_to_dict(labels: list[types.Label]) -> dict[str, str]:
    """Convert a list of Label objects to a dictionary for easier comparison"""
    return {label.id: label.label for label in labels}


@pytest.mark.asyncio
async def test_get_labels_returns_only_green_score_relevant_labels(mock_labels_taxonomy):
    """Test that get_labels returns only labels relevant for green-score computation"""
    result = await recipes.get_labels("en")
    assert isinstance(result, list)
    assert all(isinstance(label, types.Label) for label in result)
    label_ids = {label.id for label in result}
    expected_labels = {
        "en:demeter",
        "en:eu-organic",
        "en:fairtrade-international",
        "en:rainforest-alliance",
        "en:responsible-aquaculture-asc",
        "en:sustainable-fishing-method",
        "en:sustainable-seafood-msc",
        "en:utz-certified",
        "fr:ab-agriculture-biologique",
        "fr:bio-coherence",
        "fr:bio-equitable",
        "fr:bleu-blanc-coeur",
        "fr:haute-valeur-environnementale",
        "fr:label-rouge",
        "fr:nature-et-progres",
        "en:fj-bio-130",
    }
    assert label_ids == expected_labels


@pytest.mark.asyncio
async def test_get_labels_uses_correct_language_labels(mock_labels_taxonomy):
    """Test that get_labels returns labels in requested language"""
    result_en = await recipes.get_labels("en")
    result_fr = await recipes.get_labels("fr")
    en_labels = label_list_to_dict(result_en)
    fr_labels = label_list_to_dict(result_fr)
    assert en_labels["en:demeter"] == "Demeter"
    assert en_labels["en:eu-organic"] == "EU Organic"
    assert en_labels["en:fairtrade-international"] == "Fairtrade International"
    assert fr_labels["fr:nature-et-progres"] == "Nature et Progrès"
    assert fr_labels["fr:bio-coherence"] == "Bio-Cohérence"
    assert fr_labels["fr:haute-valeur-environnementale"] == "Haute Valeur Environnementale"


@pytest.mark.asyncio
async def test_get_labels_handles_language_code_with_region(mock_labels_taxonomy):
    """Test that get_labels strips region from language code (e.g. fr-FR -> fr)"""
    result_fr = await recipes.get_labels("fr")
    result_frFR = await recipes.get_labels("fr_FR")
    assert label_list_to_dict(result_fr) == label_list_to_dict(result_frFR)


def test_get_labels_api_cache_control_header(mock_labels_taxonomy):
    """Test that /v1/labels returns Cache-Control header for 1 day"""
    response = client.get("/v1/labels", params={"lang": "en"})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400"


@pytest.mark.asyncio
async def test_get_labels_excludes_synonyms_by_default(mock_labels_taxonomy):
    """Test that get_labels does not populate synonyms when include_synonyms is False"""
    result = await recipes.get_labels("en")
    assert all(label.synonyms is None for label in result)


@pytest.mark.asyncio
async def test_get_labels_includes_synonyms_when_requested(mock_labels_taxonomy):
    """Test that get_labels populates synonyms in the requested language"""
    result = await recipes.get_labels("en", include_synonyms=True)
    synonyms_by_id = {label.id: label.synonyms for label in result}
    # en:demeter has a single english synonym 'Demeter'
    assert synonyms_by_id["en:demeter"] == ["Demeter"]
    # en:fairtrade-international english synonyms
    assert synonyms_by_id["en:fairtrade-international"] == [
        "Fairtrade International",
        "Fairtrade",
        "FLO international",
        "FLO",
    ]


@pytest.mark.asyncio
async def test_get_labels_synonyms_language_fallback(mock_labels_taxonomy):
    """Test that synonyms are returned in the requested language when available"""
    result_fr = await recipes.get_labels("fr", include_synonyms=True)
    synonyms_by_id = {label.id: label.synonyms for label in result_fr}
    # fr:label-rouge only has 'xx' and 'fr' synonyms
    assert synonyms_by_id["fr:label-rouge"] == ["Label Rouge"]


def test_get_labels_api_synonyms_excluded_by_default(mock_labels_taxonomy):
    """Test that /v1/labels omits the synonyms field by default"""
    response = client.get("/v1/labels", params={"lang": "en"})
    assert response.status_code == 200
    for label in response.json()["labels"]:
        assert "synonyms" not in label


def test_get_labels_api_returns_synonyms_when_requested(mock_labels_taxonomy):
    """Test that /v1/labels includes synonyms when include_synonyms=true"""
    response = client.get("/v1/labels", params={"lang": "en", "include_synonyms": "true"})
    assert response.status_code == 200
    synonyms_by_id = {label["id"]: label["synonyms"] for label in response.json()["labels"]}
    assert synonyms_by_id["en:demeter"] == ["Demeter"]


def test_get_labels_api_invalid_language_returns_422(mock_labels_taxonomy):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    response = client.get("/v1/labels", params={"lang": "zz"})
    assert response.status_code == 422
