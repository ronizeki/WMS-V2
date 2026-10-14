"""Inbound flows: purchase orders, goods receipts, putaway, idempotency."""
from __future__ import annotations

from tests.conftest import API


def _supplier(client, tenant, code="SUP-1"):
    resp = client.post(f"{API}/suppliers", headers=tenant["headers"],
                       json={"code": code, "name": f"Supplier {code}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _position(client, tenant, warehouse, product_id, location_id=None):
    params = {"warehouse_id": warehouse["warehouse"]["id"], "product_id": product_id}
    if location_id:
        params["location_id"] = location_id
    resp = client.get(f"{API}/inventory/position", headers=tenant["headers"], params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_purchase_order_receipt_and_putaway(client, tenant, warehouse, product_factory):
    product = product_factory("INB-1")
    supplier = _supplier(client, tenant)

    po = client.post(f"{API}/purchase-orders", headers=tenant["headers"], json={
        "supplier_id": supplier["id"],
        "warehouse_id": warehouse["warehouse"]["id"],
        "lines": [{"product_id": product["id"], "ordered_qty": 100, "unit_cost": 90}],
    })
    assert po.status_code == 201, po.text
    po_body = po.json()
    assert po_body["status"] == "pending"

    approved = client.post(f"{API}/purchase-orders/{po_body['id']}/approve", headers=tenant["headers"])
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    receipt = client.post(f"{API}/goods-receipts", headers=tenant["headers"],
                          json={"warehouse_id": warehouse["warehouse"]["id"],
                                "purchase_order_id": po_body["id"]})
    assert receipt.status_code == 201, receipt.text
    receipt_body = receipt.json()
    assert receipt_body["lines"][0]["received_qty"] == 100

    posted = client.post(f"{API}/goods-receipts/{receipt_body['id']}/post", headers=tenant["headers"])
    assert posted.status_code == 200, posted.text
    assert posted.json()["posted"] is True

    # Stock landed in the receiving location
    assert _position(client, tenant, warehouse, product["id"],
                     warehouse["locations"]["RECV-01"])["on_hand"] == 100

    # PO marked received
    po_after = client.get(f"{API}/purchase-orders/{po_body['id']}", headers=tenant["headers"]).json()
    assert po_after["status"] == "received"
    assert po_after["lines"][0]["received_qty"] == 100

    # A putaway task was auto-created
    tasks = client.get(f"{API}/putaway", headers=tenant["headers"]).json()["items"]
    assert len(tasks) == 1
    task = tasks[0]
    assert task["status"] == "pending"

    completed = client.post(f"{API}/putaway/{task['id']}/complete", headers=tenant["headers"],
                            json={"to_location_id": warehouse["locations"]["STOR-A01"]})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    assert _position(client, tenant, warehouse, product["id"],
                     warehouse["locations"]["RECV-01"])["on_hand"] == 0
    assert _position(client, tenant, warehouse, product["id"],
                     warehouse["locations"]["STOR-A01"])["on_hand"] == 100


def test_goods_receipt_post_is_idempotent(client, tenant, warehouse, product_factory):
    product = product_factory("INB-2")
    receipt = client.post(f"{API}/goods-receipts", headers=tenant["headers"], json={
        "warehouse_id": warehouse["warehouse"]["id"],
        "lines": [{"product_id": product["id"], "received_qty": 25,
                   "receiving_location_id": warehouse["locations"]["STOR-A01"]}],
    }).json()

    headers = {**tenant["headers"], "Idempotency-Key": "receipt-key-1"}
    first = client.post(f"{API}/goods-receipts/{receipt['id']}/post", headers=headers)
    second = client.post(f"{API}/goods-receipts/{receipt['id']}/post", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    # Only one movement should have been recorded, and stock rose exactly once
    assert _position(client, tenant, warehouse, product["id"])["on_hand"] == 25
    ledger = client.get(f"{API}/inventory/ledger", headers=tenant["headers"],
                        params={"product_id": product["id"]}).json()["items"]
    assert len(ledger) == 1


def test_damaged_receipt_tracks_damaged_bucket(client, tenant, warehouse, product_factory):
    product = product_factory("INB-3")
    receipt = client.post(f"{API}/goods-receipts", headers=tenant["headers"], json={
        "warehouse_id": warehouse["warehouse"]["id"],
        "lines": [{"product_id": product["id"], "received_qty": 30, "damaged_qty": 10,
                   "receiving_location_id": warehouse["locations"]["STOR-A01"]}],
    }).json()
    client.post(f"{API}/goods-receipts/{receipt['id']}/post", headers=tenant["headers"])

    position = _position(client, tenant, warehouse, product["id"])
    # good 20 in stock, 10 damaged (total on hand 30 but unavailable 20)
    assert position["on_hand"] == 30
    assert position["damaged"] == 10
    assert position["available"] == 20
