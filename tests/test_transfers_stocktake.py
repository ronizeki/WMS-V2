"""Transfers and cycle count (stocktake) flows."""
from __future__ import annotations

from tests.conftest import API, receive_stock


def _position(client, tenant, warehouse, product_id, location_code):
    resp = client.get(f"{API}/inventory/position", headers=tenant["headers"], params={
        "warehouse_id": warehouse["warehouse"]["id"],
        "product_id": product_id,
        "location_id": warehouse["locations"][location_code],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_transfer_dispatch_and_receive(client, tenant, warehouse, product_factory):
    product = product_factory("TRF-1")
    receive_stock(client, tenant, warehouse, product, 30, "STOR-A01")

    transfer = client.post(f"{API}/transfers", headers=tenant["headers"], json={
        "from_warehouse_id": warehouse["warehouse"]["id"],
        "from_location_id": warehouse["locations"]["STOR-A01"],
        "to_warehouse_id": warehouse["warehouse"]["id"],
        "to_location_id": warehouse["locations"]["STOR-A02"],
        "lines": [{"product_id": product["id"], "requested_qty": 12}],
    })
    assert transfer.status_code == 201, transfer.text
    body = transfer.json()

    dispatched = client.post(f"{API}/transfers/{body['id']}/dispatch", headers=tenant["headers"])
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "in_transit"
    # source reduced, destination holds it as in-transit
    assert _position(client, tenant, warehouse, product["id"], "STOR-A01")["on_hand"] == 18
    assert _position(client, tenant, warehouse, product["id"], "STOR-A02")["in_transit"] == 12

    line_id = dispatched.json()["lines"][0]["id"]
    received = client.post(f"{API}/transfers/{body['id']}/receive", headers=tenant["headers"],
                           json={"lines": [{"line_id": line_id, "received_qty": 12}]})
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "completed"
    dest = _position(client, tenant, warehouse, product["id"], "STOR-A02")
    assert dest["on_hand"] == 12
    assert dest["in_transit"] == 0


def test_transfer_requires_approval_when_configured(client, tenant, warehouse, product_factory,
                                                    platform_headers):
    product = product_factory("TRF-2")
    receive_stock(client, tenant, warehouse, product, 20, "STOR-A01")
    client.patch(f"{API}/platform/tenants/{tenant['id']}", headers=platform_headers,
                 json={"settings": {"require_transfer_approval": True}})

    transfer = client.post(f"{API}/transfers", headers=tenant["headers"], json={
        "from_warehouse_id": warehouse["warehouse"]["id"],
        "from_location_id": warehouse["locations"]["STOR-A01"],
        "to_warehouse_id": warehouse["warehouse"]["id"],
        "to_location_id": warehouse["locations"]["STOR-A02"],
        "lines": [{"product_id": product["id"], "requested_qty": 5}],
    }).json()
    assert transfer["approval_status"] == "pending"

    blocked = client.post(f"{API}/transfers/{transfer['id']}/dispatch", headers=tenant["headers"])
    assert blocked.status_code == 422

    client.post(f"{API}/transfers/{transfer['id']}/approve", headers=tenant["headers"])
    allowed = client.post(f"{API}/transfers/{transfer['id']}/dispatch", headers=tenant["headers"])
    assert allowed.status_code == 200


def test_cycle_count_posts_variance_adjustment(client, tenant, warehouse, product_factory):
    product = product_factory("CC-1")
    receive_stock(client, tenant, warehouse, product, 40, "STOR-A01")

    count = client.post(f"{API}/cycle-counts", headers=tenant["headers"], json={
        "warehouse_id": warehouse["warehouse"]["id"],
        "location_id": warehouse["locations"]["STOR-A01"],
    })
    assert count.status_code == 201, count.text
    body = count.json()
    assert body["lines"][0]["system_qty"] == 40

    line_id = body["lines"][0]["id"]
    counted = client.post(f"{API}/cycle-counts/{body['id']}/count", headers=tenant["headers"],
                          json={"lines": [{"line_id": line_id, "counted_qty": 36}]})
    assert counted.status_code == 200, counted.text
    assert counted.json()["lines"][0]["variance_qty"] == -4

    approved = client.post(f"{API}/cycle-counts/{body['id']}/approve", headers=tenant["headers"])
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "completed"
    assert _position(client, tenant, warehouse, product["id"], "STOR-A01")["on_hand"] == 36

    ledger = client.get(f"{API}/inventory/ledger", headers=tenant["headers"],
                        params={"product_id": product["id"],
                                "movement_type": "cycle_count_adjustment"}).json()["items"]
    assert len(ledger) == 1
    assert ledger[0]["quantity"] == -4
