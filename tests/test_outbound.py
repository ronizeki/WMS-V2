"""Outbound flows: allocation, picking, packing, shipping and idempotency."""
from __future__ import annotations

from tests.conftest import API, receive_stock


def _customer(client, tenant, code="CUS-1"):
    resp = client.post(f"{API}/customers", headers=tenant["headers"],
                       json={"code": code, "name": f"Customer {code}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _order(client, tenant, warehouse, product_id, qty=10):
    customer = _customer(client, tenant)
    resp = client.post(f"{API}/sales-orders", headers=tenant["headers"], json={
        "customer_id": customer["id"],
        "warehouse_id": warehouse["warehouse"]["id"],
        "lines": [{"product_id": product_id, "ordered_qty": qty, "unit_price": 200}],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _balance(client, tenant, product_id):
    items = client.get(f"{API}/inventory/balances", headers=tenant["headers"],
                       params={"product_id": product_id}).json()["items"]
    return items[0] if items else None


def test_full_fulfillment_flow(client, tenant, warehouse, product_factory):
    product = product_factory("OUT-1")
    receive_stock(client, tenant, warehouse, product, 50, "STOR-A01")

    order = _order(client, tenant, warehouse, product["id"], qty=20)
    assert order["status"] == "draft"
    client.post(f"{API}/sales-orders/{order['id']}/confirm", headers=tenant["headers"])

    allocation = client.post(f"{API}/sales-orders/{order['id']}/allocate", headers=tenant["headers"])
    assert allocation.status_code == 200, allocation.text
    assert allocation.json()["picking_task"]["status"] == "pending"
    balance = _balance(client, tenant, product["id"])
    assert balance["quantity_reserved"] == 20
    assert balance["quantity_available"] == 30

    tasks = client.get(f"{API}/picking", headers=tenant["headers"]).json()["items"]
    task = tasks[0]
    client.post(f"{API}/picking/{task['id']}/start", headers=tenant["headers"])
    completed = client.post(f"{API}/picking/{task['id']}/complete", headers=tenant["headers"],
                            json={"lines": [{"line_id": task["lines"][0]["id"], "picked_qty": 20}]})
    assert completed.status_code == 200, completed.text

    packing = client.post(f"{API}/sales-orders/{order['id']}/packing", headers=tenant["headers"])
    assert packing.status_code == 201, packing.text
    packing_id = packing.json()["id"]
    packed = client.post(f"{API}/packing/{packing_id}/complete", headers=tenant["headers"],
                         json={"package_count": 2})
    assert packed.status_code == 200, packed.text

    shipment = client.post(f"{API}/shipments", headers=tenant["headers"],
                           json={"sales_order_id": order["id"]}).json()
    posted = client.post(f"{API}/shipments/{shipment['id']}/post", headers=tenant["headers"])
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "in_transit"

    balance = _balance(client, tenant, product["id"])
    assert balance["quantity_on_hand"] == 30
    assert balance["quantity_reserved"] == 0
    assert balance["quantity_available"] == 30

    order_after = client.get(f"{API}/sales-orders/{order['id']}", headers=tenant["headers"]).json()
    assert order_after["status"] == "shipped"
    assert order_after["lines"][0]["shipped_qty"] == 20


def test_shipment_post_is_idempotent(client, tenant, warehouse, product_factory):
    product = product_factory("OUT-2")
    receive_stock(client, tenant, warehouse, product, 40, "STOR-A01")
    order = _order(client, tenant, warehouse, product["id"], qty=15)
    client.post(f"{API}/sales-orders/{order['id']}/allocate", headers=tenant["headers"])
    shipment = client.post(f"{API}/shipments", headers=tenant["headers"],
                           json={"sales_order_id": order["id"]}).json()

    headers = {**tenant["headers"], "Idempotency-Key": "ship-key-1"}
    first = client.post(f"{API}/shipments/{shipment['id']}/post", headers=headers)
    second = client.post(f"{API}/shipments/{shipment['id']}/post", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    # Stock is only decremented once despite the double post
    balance = _balance(client, tenant, product["id"])
    assert balance["quantity_on_hand"] == 25

    movements = client.get(f"{API}/inventory/ledger", headers=tenant["headers"],
                           params={"product_id": product["id"],
                                   "movement_type": "outbound_shipment"}).json()["items"]
    assert len(movements) == 1
    assert movements[0]["quantity"] == -15


def test_allocation_fails_when_stock_insufficient(client, tenant, warehouse, product_factory):
    product = product_factory("OUT-3")
    receive_stock(client, tenant, warehouse, product, 5, "STOR-A01")
    order = _order(client, tenant, warehouse, product["id"], qty=10)

    resp = client.post(f"{API}/sales-orders/{order['id']}/allocate", headers=tenant["headers"])
    assert resp.status_code == 409
    assert resp.json()["code"] == "insufficient_stock"

    # nothing should remain reserved after a failed allocation
    balance = _balance(client, tenant, product["id"])
    assert balance["quantity_reserved"] == 0


def test_allocation_spans_multiple_locations(client, tenant, warehouse, product_factory):
    product = product_factory("OUT-4")
    receive_stock(client, tenant, warehouse, product, 6, "STOR-A01")
    receive_stock(client, tenant, warehouse, product, 6, "STOR-A02")
    order = _order(client, tenant, warehouse, product["id"], qty=10)

    resp = client.post(f"{API}/sales-orders/{order['id']}/allocate", headers=tenant["headers"])
    assert resp.status_code == 200, resp.text
    allocated_locations = {line["location_id"] for line in resp.json()["picking_task"]["lines"]}
    assert len(allocated_locations) == 2


def test_cancel_order_releases_reservation(client, tenant, warehouse, product_factory):
    product = product_factory("OUT-5")
    receive_stock(client, tenant, warehouse, product, 30, "STOR-A01")
    order = _order(client, tenant, warehouse, product["id"], qty=12)
    client.post(f"{API}/sales-orders/{order['id']}/allocate", headers=tenant["headers"])
    assert _balance(client, tenant, product["id"])["quantity_reserved"] == 12

    client.post(f"{API}/sales-orders/{order['id']}/cancel", headers=tenant["headers"])
    balance = _balance(client, tenant, product["id"])
    assert balance["quantity_reserved"] == 0
    assert balance["quantity_available"] == 30
