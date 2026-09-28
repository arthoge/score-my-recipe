"""Tests for the ``GET /v1/suggest-scored-ingredient`` HTTP endpoint."""

from fastapi.testclient import TestClient

import openfoodfacts.taxonomy as taxonomy

from api.api import app
from tests.helpers import patch_ingredients_taxonomy, patch_language_check

client = TestClient(app)


def build_taxonomy(data: dict) -> taxonomy.Taxonomy:
    """Build a real ``Taxonomy`` from a dict (OFF taxonomy JSON format)."""
    return taxonomy.Taxonomy.from_dict(data)


def test_api_returns_alternatives(agribalyse_index):
    """The endpoint returns descendants that resolve to an Agribalyse row,
    each annotated with the Agribalyse row code, as ingredients."""
    data = {
        "en:fruit": {"name": {"en": "Fruit"}, "agribalyse_food_code": {"en": "10001"}},
        "en:pear": {
            "name": {"en": "Pear"},
            "parents": ["en:fruit"],
            "agribalyse_food_code": {"en": "10002"},
        },
    }
    tax = build_taxonomy(data)
    with patch_ingredients_taxonomy(tax), patch_language_check():
        response = client.get(
            "/v1/suggest-scored-ingredient",
            params={"lang": "en", "taxonomy_id": "en:fruit"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ingredients"] == [
        {"id": "en:fruit", "label": "Fruit", "agribalyseCode": "10001"},
        {"id": "en:pear", "label": "Pear", "agribalyseCode": "10002"},
    ]


def test_api_include_synonyms(agribalyse_index):
    """include_synonyms=True returns the synonyms list, like get_ingredients."""
    data = {
        "en:fruit": {
            "name": {"en": "Fruit"},
            "synonyms": {"en": ["fruits"]},
            "agribalyse_food_code": {"en": "10001"},
        },
    }
    tax = build_taxonomy(data)
    with patch_ingredients_taxonomy(tax), patch_language_check():
        response = client.get(
            "/v1/suggest-scored-ingredient",
            params={"lang": "en", "taxonomy_id": "en:fruit", "include_synonyms": "true"},
        )
    assert response.status_code == 200
    item = response.json()["ingredients"][0]
    assert item["synonyms"] == ["fruits"]


def test_api_unknown_taxonomy_id_returns_empty(agribalyse_index):
    """An unknown taxonomy id yields an empty list, not an error."""
    with patch_ingredients_taxonomy(build_taxonomy({})), patch_language_check():
        response = client.get(
            "/v1/suggest-scored-ingredient",
            params={"lang": "en", "taxonomy_id": "en:missing"},
        )
    assert response.status_code == 200
    assert response.json()["ingredients"] == []


def test_api_no_match_returns_empty(agribalyse_index):
    """A taxonomy id with no Agribalyse match in its subtree yields an empty list."""
    data = {"en:water": {"name": {"en": "Water"}}}
    with patch_ingredients_taxonomy(build_taxonomy(data)), patch_language_check():
        response = client.get(
            "/v1/suggest-scored-ingredient",
            params={"lang": "en", "taxonomy_id": "en:water"},
        )
    assert response.status_code == 200
    assert response.json()["ingredients"] == []


def test_api_invalid_language_returns_422(agribalyse_index):
    """An unsupported language code (lang=zz) is rejected with HTTP 422."""
    with patch_ingredients_taxonomy(build_taxonomy({})), patch_language_check():
        response = client.get(
            "/v1/suggest-scored-ingredient",
            params={"lang": "zz", "taxonomy_id": "en:fruit"},
        )
    assert response.status_code == 422
