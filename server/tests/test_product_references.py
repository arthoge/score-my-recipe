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
async def test_off_proxy_request(monkeypatch):
    """Search requests carry language, identifier fields, timeout and the project's user agent."""
    requests = []

    def open_response(request, timeout):
        """Return a real search-shaped response without network access."""
        requests.append((request, timeout))
        return BytesIO(b'{"hits": [{"code": "123", "product_name": "Rice"}]}')

    monkeypatch.setattr(off.urllib.request, "urlopen", open_response)
    off.search_products.cache_clear()
    try:
        assert await off.search_products("rice", "en", 3) == [
            {"code": "123", "product_name": "Rice"}
        ]
        await off.search_products("rice", "en", 3)
        assert len(requests) == 1
        request, timeout = requests[0]
        params = parse_qs(urlparse(request.full_url).query)
        assert params["q"] == ["rice"]
        assert params["langs"] == ["en"]
        assert params["page_size"] == ["3"]
        assert "code" in params["fields"][0]
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
