"""API validation, error handling and report endpoints."""
from __future__ import annotations

from tests.conftest import API, receive_stock


def test_missing_required_fields_returns_422(client, tenant):
    resp = client.post(f"{API}/products", headers=tenant["headers"], json={"name": "No SKU"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_duplicate_sku_returns_409(client, tenant, product_factory):
    product_factory("DUP-1")
    resp = client.post(f"{API}/products", headers=tenant["headers"],
                       json={"sku": "DUP-1", "name": "Duplicate"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "conflict"


def test_unknown_resource_returns_404(client, tenant):
    resp = client.get(f"{API}/products/does-not-exist", headers=tenant["headers"])
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_invalid_adjustment_type_rejected(client, tenant, warehouse, product_factory):
    product = product_factory("VAL-1")
    resp = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"], json={
        "warehouse_id": warehouse["warehouse"]["id"],
        "location_id": warehouse["locations"]["STOR-A01"],
        "product_id": product["id"],
        "adjustment_type": "teleport",
        "quantity": 1,
    })
    assert resp.status_code == 422


def test_adjustment_location_must_belong_to_warehouse(client, tenant, warehouse, product_factory):
    product = product_factory("VAL-2")
    other = client.post(f"{API}/warehouses", headers=tenant["headers"],
                        json={"code": "OTHER", "name": "Other"}).json()
    resp = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"], json={
        "warehouse_id": other["id"],
        "location_id": warehouse["locations"]["STOR-A01"],
        "product_id": product["id"],
        "adjustment_type": "increase",
        "quantity": 1,
    })
    assert resp.status_code == 404


def test_barcode_lookup(client, tenant, product_factory):
    product = product_factory("VAL-3", barcode="8880001112223")
    found = client.get(f"{API}/products/lookup", headers=tenant["headers"],
                       params={"code": "8880001112223"})
    assert found.status_code == 200
    assert found.json()["id"] == product["id"]

    missing = client.get(f"{API}/products/lookup", headers=tenant["headers"],
                         params={"code": "0000000000000"})
    assert missing.status_code == 404


def test_dashboard_reports_kpis(client, tenant, warehouse, product_factory):
    product = product_factory("DASH-1", reorder_point=100)
    receive_stock(client, tenant, warehouse, product, 30)

    resp = client.get(f"{API}/dashboard", headers=tenant["headers"])
    assert resp.status_code == 200, resp.text
    kpis = resp.json()["kpis"]
    assert kpis["total_products"] == 1
    assert kpis["total_warehouses"] == 1
    assert kpis["low_stock_count"] == 1
    assert kpis["inventory_value"] > 0


def test_inventory_value_report(client, tenant, warehouse, product_factory):
    product = product_factory("REP-1", cost_price=1000.0)
    receive_stock(client, tenant, warehouse, product, 10, unit_cost=1000.0)
    resp = client.get(f"{API}/reports/inventory-value", headers=tenant["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_value"] == 10000.0
    assert body["total_on_hand"] == 10


def test_stock_movement_report(client, tenant, warehouse, product_factory):
    product = product_factory("REP-2")
    receive_stock(client, tenant, warehouse, product, 25)
    resp = client.get(f"{API}/reports/stock-movements", headers=tenant["headers"])
    assert resp.status_code == 200
    assert resp.json()["total_in"] == 25


def test_audit_log_records_mutations(client, tenant, warehouse):
    client.post(f"{API}/warehouses/{warehouse['warehouse']['id']}/locations",
                headers=tenant["headers"], json={"code": "NEW-1"})
    resp = client.get(f"{API}/audit-logs", headers=tenant["headers"],
                      params={"entity_type": "location"})
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] >= 1
