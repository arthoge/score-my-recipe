"""Tests for catalog-backed Make it better recommendations."""

from fastapi.testclient import TestClient

from api.api import app


client = TestClient(app)


def test_api_returns_the_best_catalogued_improvement():
    """The option with the greatest combined score gain is returned."""
    response = client.post(
        "/v1/make-it-better/check",
        json={"ingredients": ["Chocolate yogurt", "Tomato"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["noImprovement"] == ["Tomato"]
    suggestion = body["suggestions"][0]
    assert suggestion["original"]["name"] == "Chocolate yogurt"
    assert suggestion["suggested"]["name"] == "Organic plain yogurt"
    assert suggestion["improvements"] == [
        {"label": "Nutri-Score", "fromScore": "D", "toScore": "A"},
        {"label": "Green-Score", "fromScore": "D", "toScore": "A"},
    ]


def test_api_returns_no_suggestions_for_unknown_products():
    """Products outside the explicit catalog remain unchanged."""
    response = client.post("/v1/make-it-better/check", json={"ingredients": ["Tomato"]})

    assert response.status_code == 200
    assert response.json() == {"suggestions": [], "noImprovement": ["Tomato"]}
