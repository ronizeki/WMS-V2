"""Inventory engine: balances, ledger integrity, adjustments and invariants."""
from __future__ import annotations

from tests.conftest import API, receive_stock


def _balance(client, tenant, product_id):
    resp = client.get(f"{API}/inventory/balances",
                      headers=tenant["headers"], params={"product_id": product_id})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def test_receipt_increases_on_hand_and_records_ledger(client, tenant, warehouse, product_factory):
    product = product_factory("INV-1")
    receive_stock(client, tenant, warehouse, product, 40, "STOR-A01")

    balances = _balance(client, tenant, product["id"])
    assert len(balances) == 1
    balance = balances[0]
    assert balance["quantity_on_hand"] == 40
    assert balance["quantity_available"] == 40
    assert balance["quantity_reserved"] == 0

    ledger = client.get(f"{API}/inventory/ledger", headers=tenant["headers"],
                        params={"product_id": product["id"]}).json()["items"]
    assert len(ledger) == 1
    assert ledger[0]["movement_type"] == "inbound_receipt"
    assert ledger[0]["quantity_before"] == 0
    assert ledger[0]["quantity_after"] == 40


def test_available_equals_on_hand_minus_reserved(client, tenant, warehouse, product_factory):
    product = product_factory("INV-2")
    receive_stock(client, tenant, warehouse, product, 30)

    # reserve 10 via allocation to prove the invariant
    customer = client.post(f"{API}/customers", headers=tenant["headers"],
                           json={"code": "C1", "name": "Customer"}).json()
    order = client.post(f"{API}/sales-orders", headers=tenant["headers"],
                        json={"customer_id": customer["id"], "warehouse_id": warehouse["warehouse"]["id"],
                              "lines": [{"product_id": product["id"], "ordered_qty": 10}]})
    assert order.status_code == 201, order.text
    allocated = client.post(f"{API}/sales-orders/{order.json()['id']}/allocate",
                            headers=tenant["headers"])
    assert allocated.status_code == 200, allocated.text

    balance = _balance(client, tenant, product["id"])[0]
    assert balance["quantity_reserved"] == 10
    assert balance["quantity_available"] == 20
    assert balance["quantity_on_hand"] == 30


def test_adjustment_increase_and_decrease(client, tenant, warehouse, product_factory):
    product = product_factory("INV-3")
    receive_stock(client, tenant, warehouse, product, 20)

    base = {"warehouse_id": warehouse["warehouse"]["id"],
            "location_id": warehouse["locations"]["STOR-A01"], "product_id": product["id"]}

    inc = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"],
                      json={**base, "adjustment_type": "increase", "quantity": 5,
                            "reason": "found"})
    assert inc.status_code == 201, inc.text
    assert inc.json()["posted"] is True
    assert _balance(client, tenant, product["id"])[0]["quantity_on_hand"] == 25

    dec = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"],
                      json={**base, "adjustment_type": "decrease", "quantity": 5,
                            "reason": "damage"})
    assert dec.status_code == 201, dec.text
    assert _balance(client, tenant, product["id"])[0]["quantity_on_hand"] == 20


def test_cannot_drive_stock_negative(client, tenant, warehouse, product_factory):
    product = product_factory("INV-4")
    receive_stock(client, tenant, warehouse, product, 3)

    resp = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"],
                       json={"warehouse_id": warehouse["warehouse"]["id"],
                             "location_id": warehouse["locations"]["STOR-A01"],
                             "product_id": product["id"],
                             "adjustment_type": "decrease", "quantity": 10,
                             "reason": "loss"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "insufficient_stock"
    assert _balance(client, tenant, product["id"])[0]["quantity_on_hand"] == 3


def test_adjustment_approval_workflow(client, tenant, warehouse, product_factory, platform_headers):
    product = product_factory("INV-5")
    receive_stock(client, tenant, warehouse, product, 10)

    # Turn on approval requirement for this tenant
    patched = client.patch(f"{API}/platform/tenants/{tenant['id']}", headers=platform_headers,
                           json={"settings": {"require_adjustment_approval": True}})
    assert patched.status_code == 200, patched.text

    base = {"warehouse_id": warehouse["warehouse"]["id"],
            "location_id": warehouse["locations"]["STOR-A01"], "product_id": product["id"]}

    created = client.post(f"{API}/inventory/adjustments", headers=tenant["headers"],
                          json={**base, "adjustment_type": "increase", "quantity": 7})
    assert created.status_code == 201, created.text
    adjustment = created.json()
    assert adjustment["status"] == "pending_approval"
    assert adjustment["posted"] is False
    # stock must be unchanged until approved
    assert _balance(client, tenant, product["id"])[0]["quantity_on_hand"] == 10

    approved = client.post(f"{API}/inventory/adjustments/{adjustment['id']}/approve",
                           headers=tenant["headers"])
    assert approved.status_code == 200, approved.text
    assert approved.json()["posted"] is True
    assert _balance(client, tenant, product["id"])[0]["quantity_on_hand"] == 17


def test_inventory_summary_aggregates_across_locations(client, tenant, warehouse, product_factory):
    product = product_factory("INV-6")
    receive_stock(client, tenant, warehouse, product, 10, "STOR-A01")
    receive_stock(client, tenant, warehouse, product, 15, "STOR-A02")

    resp = client.get(f"{API}/inventory/summary", headers=tenant["headers"])
    assert resp.status_code == 200
    row = next(r for r in resp.json()["items"] if r["product_id"] == product["id"])
    assert row["on_hand"] == 25
    assert row["available"] == 25


def test_stock_position_endpoint(client, tenant, warehouse, product_factory):
    product = product_factory("INV-7")
    receive_stock(client, tenant, warehouse, product, 12)
    resp = client.get(f"{API}/inventory/position", headers=tenant["headers"],
                      params={"warehouse_id": warehouse["warehouse"]["id"],
                              "product_id": product["id"]})
    assert resp.status_code == 200
    assert resp.json()["on_hand"] == 12
    assert resp.json()["available"] == 12
