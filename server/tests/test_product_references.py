"""Test genuine OFF product identities, localized labels and bounded proxy requests."""

from io import BytesIO
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse
import pytest
from fastapi.testclient import TestClient
from api import off, references
from api.api import app


@pytest.mark.asyncio
async def test_product_names_and_order(monkeypatch):
    """Keep OFF relevance order, skip unidentifiable hits and display localized names and brands."""
    search = AsyncMock(
        return_value=[
            {
                "code": "123",
                "product_name": {"fr": "Tomates", "en": "Tomatoes"},
                "brands": ["Brand"],
            },
            {"product_name": "No code"},
            {"code": "bad", "product_name": ""},
            {"code": "456", "product_name_fr": "Purée", "product_name": "Puree", "brands": "Other"},
        ]
    )
    monkeypatch.setattr(off, "search_products", search)
    result = await references.product_references(" tomates ", "fr", 8)
    assert [(food.code, food.name) for food in result.foods] == [
        ("123", "Tomates — Brand"),
        ("456", "Purée — Other"),
    ]
    search.assert_awaited_once_with("tomates", "fr", 8)
    assert (await references.product_references(" ", "fr", 8)).foods == []
    assert search.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["rice", "rice OR milk", 'brands:"Other" rice'])
async def test_off_proxy_request(monkeypatch, query):
    """Food-only searches preserve language, limits, caching and request metadata."""
    requests = []

    def open_response(request, timeout):
        """Return a real search-shaped response without network access."""
        requests.append((request, timeout))
        return BytesIO(
            b'{"hits": ['
            b'{"code": "123", "product_name": "Rice", "product_type": "food", "nutriments": {"energy-kcal_100g": 350}},'
            b'{"code": "456", "product_name": "Rice cream", "product_type": "beauty"},'
            b'{"code": "789", "product_name": "Dog rice", "product_type": "petfood"},'
            b'{"code": "012", "product_name": "Rice cooker", "product_type": "product"},'
            b'{"code": "345", "product_name": "Rice", "categories_tags": ["en:plant-based-foods-and-beverages", "en:rices"]},'
            b'{"code": "678", "product_name": "Rice shampoo", "categories_tags": ["en:cosmetics"]}, null]}'
        )

    monkeypatch.setattr(off.urllib.request, "urlopen", open_response)
    off.search_products.cache_clear()
    try:
        assert await off.search_products(query, "en", 3) == [
            {
                "code": "123",
                "product_name": "Rice",
                "product_type": "food",
                "nutriments": {"energy-kcal_100g": 350},
            },
            {
                "code": "345",
                "product_name": "Rice",
                "categories_tags": ["en:plant-based-foods-and-beverages", "en:rices"],
            },
        ]
        await off.search_products(query, "en", 3)
        assert len(requests) == 1
        request, timeout = requests[0]
        params = parse_qs(urlparse(request.full_url).query)
        assert params["q"] == [query]
        assert params["index_id"] == ["off"]
        assert params["langs"] == ["en"]
        assert params["page_size"] == ["9"]
        assert "code" in params["fields"][0]
        assert "product_type" in params["fields"][0].split(",")
        assert "nutriments" in params["fields"][0].split(",")
        assert request.get_header("User-agent") == off.USER_AGENT
        assert timeout == 10
    finally:
        off.search_products.cache_clear()


def test_product_api_failure_and_validation(monkeypatch):
    """Report unavailable OFF service without presenting fake suggestions."""
    monkeypatch.setattr(off, "search_products", AsyncMock(side_effect=OSError("offline")))
    client = TestClient(app)
    assert client.get("/v1/nutrition/products", params={"q": "rice"}).status_code == 502
    assert client.get("/v1/nutrition/products", params={"q": ""}).json() == {"foods": []}
    assert client.get("/v1/nutrition/products", params={"limit": 0}).status_code == 422


@pytest.mark.parametrize(
    "product",
    [
        {"code": "8710847994159", "product_name": "CIF Floor Cleaner"},
        {"code": "8710847994159", "product_name": "CIF Floor Cleaner", "product_type": "food"},
        {"product_type": "food", "categories_tags": [], "nutriments": {}},
        {"categories_tags": ["en:shampoos"]},
        {"product_type": "beauty", "nutriments": {"fat_100g": 10}},
        {"categories_tags": ["en:cleaning-products"], "nutriments": {"fat_100g": 10}},
        {"nutriments": {"fat_100g": None}},
        {"nutriments": {"fat_100g": -1}},
        {"nutriments": {"fat_100g": float("nan")}},
        {"nutriments": {"fat_100g": True}},
    ],
)
def test_non_food_and_unverified_products_are_not_suggested(product):
    """CIF's live incomplete record and unknown products must never become automatic food matches."""
    assert not off.is_food_product(product)


@pytest.mark.parametrize(
    "product",
    [
        {"categories_tags": ["en:plant-based-foods-and-beverages", "en:rices"]},
        {"categories_tags": ["en:beverages"]},
        {"nutriments": {"energy-kcal_100g": 350}},
        {"nutriments": {"fat_100g": 0}},
    ],
)
def test_food_evidence_preserves_legitimate_products(product):
    """Food families or measured nutrition facts keep real products searchable without product_type."""
    assert off.is_food_product(product)


@pytest.mark.asyncio
async def test_cleaner_is_skipped_before_selecting_a_food(monkeypatch):
    """An unclassified cleaner preceding a genuine food must not take the automatic selection slot."""
    import json

    hits = [
        {"code": "8710847994159", "product_name": "CIF Floor Cleaner", "product_type": "food"},
        {
            "code": "123",
            "product_name": "Rice",
            "categories_tags": ["en:plant-based-foods-and-beverages"],
        },
    ]
    monkeypatch.setattr(
        off.urllib.request,
        "urlopen",
        lambda *args, **kwargs: BytesIO(json.dumps({"hits": hits}).encode()),
    )
    off.search_products.cache_clear()
    try:
        result = await references.product_references("floor", "en", 1)
        assert [(food.code, food.name) for food in result.foods] == [("123", "Rice")]
    finally:
        off.search_products.cache_clear()
