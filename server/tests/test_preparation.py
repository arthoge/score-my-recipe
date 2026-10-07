"""Verify narrow yield matching, edible weight handling and the HTTP contract."""

import pytest
from fastapi.testclient import TestClient
from api.api import app
from api import ciqual, preparation


@pytest.mark.parametrize(
    "code,method,expected",
    [
        ("9119", "boiled", 298),
        ("9821", "boiled", 260),
        ("20359", "boiled", 273),
        ("4008", "steamed", 98),
    ],
)
def test_documented_yields(code, method, expected):
    """Each approved CIQUAL/process pair applies its cited edible-mass yield once."""
    result = preparation.estimate_prepared_weight(
        preparation.PreparedWeightRequest(quantity_g=100, ciqual_code=code, preparation=method)
    )
    assert result.status == "estimated"
    assert result.prepared_weight_g == expected
    assert result.source is not None
    assert result.source.version == "bognar-2002-v1"
    assert result.source is not None
    assert result.source.table.startswith("Table ")
    assert code in ciqual.get_foods()


@pytest.mark.parametrize("state", ["cooked", "drained"])
def test_already_prepared(state):
    """Entered cooked/drained weight is never multiplied by a raw-food yield."""
    result = preparation.estimate_prepared_weight(
        preparation.PreparedWeightRequest(
            quantity_g=150, ciqual_code="9119", preparation="boiled", state=state
        )
    )
    assert result.status == "unchanged"
    assert result.prepared_weight_g == 150
    assert result.source is None


@pytest.mark.parametrize(
    "code,method",
    [
        ("9100", "boiled"),
        ("9102", "boiled"),
        ("9815", "boiled"),
        ("4008", "deep_fried"),
        ("9119", "steamed"),
        (None, "boiled"),
    ],
)
def test_no_family_wide_or_process_guessing(code, method):
    """Generic/wholegrain rice, fresh pasta and unsupported processes stay unestimated."""
    result = preparation.estimate_prepared_weight(
        preparation.PreparedWeightRequest(quantity_g=100, ciqual_code=code, preparation=method)
    )
    assert result.status == "unsupported"
    assert result.prepared_weight_g == 100
    assert result.yield_factor is None
    assert result.source is None


def test_product_and_no_preparation():
    """An OFF nutrition reference must not suppress the selected CIQUAL cooking yield."""
    request = preparation.PreparedWeightRequest(
        quantity_g=100, ciqual_code="9119", barcode="123", preparation="boiled"
    )
    result = preparation.estimate_prepared_weight(request)
    assert result.status == "estimated"
    assert result.prepared_weight_g == 298
    request.ciqual_code = None
    assert preparation.estimate_prepared_weight(request).status == "unsupported"
    assert preparation.estimate_prepared_weight(request).prepared_weight_g == 100
    request.preparation = "none"
    assert preparation.estimate_prepared_weight(request).prepared_weight_g == 100


def test_endpoint_and_quantity_validation():
    """The endpoint returns traceable estimates and rejects invalid quantities/state/process."""
    client = TestClient(app)
    payload = {"quantity_g": 125.5, "ciqual_code": "9821", "preparation": "boiled"}
    response = client.post("/v1/prepared-weight", json=payload)
    assert response.status_code == 200
    assert response.json()["prepared_weight_g"] == pytest.approx(326.3)
    assert response.json()["source"]["conditions"]
    fallback = client.post("/v1/prepared-weight", json={**payload, "ciqual_code": "unknown"})
    assert fallback.json()["prepared_weight_g"] == 125.5
    assert fallback.json()["status"] == "unsupported"
    with_product = client.post("/v1/prepared-weight", json={**payload, "barcode": "123"})
    assert with_product.json()["prepared_weight_g"] == pytest.approx(326.3)
    for quantity in [0, -1, "NaN", "Infinity"]:
        assert (
            client.post("/v1/prepared-weight", json={**payload, "quantity_g": quantity}).status_code
            == 422
        )
    for field, value in [("state", "unknown"), ("preparation", "microwaved")]:
        assert client.post("/v1/prepared-weight", json={**payload, field: value}).status_code == 422
