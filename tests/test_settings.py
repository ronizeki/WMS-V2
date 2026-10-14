"""Tenant self-service settings."""
from __future__ import annotations

from tests.conftest import API, add_user


def test_get_settings_returns_profile_and_defaults(client, tenant):
    resp = client.get(f"{API}/settings", headers=tenant["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == tenant["id"]
    assert "settings" in body
    assert body["settings"]["costing_method"] == "weighted_average"
    assert body["settings"]["allow_negative_stock"] is False


def test_update_settings_persists_changes(client, tenant):
    resp = client.patch(
        f"{API}/settings",
        headers=tenant["headers"],
        json={
            "name": "Updated Org",
            "timezone": "Asia/Makassar",
            "currency": "USD",
            "settings": {"allow_negative_stock": True, "reservation_timeout_minutes": 45},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Updated Org"
    assert body["timezone"] == "Asia/Makassar"
    assert body["currency"] == "USD"
    assert body["settings"]["allow_negative_stock"] is True
    assert body["settings"]["reservation_timeout_minutes"] == 45
    # Unknown setting keys are ignored.
    assert body["settings"]["require_transfer_approval"] is False


def test_update_settings_ignores_unknown_keys(client, tenant):
    resp = client.patch(
        f"{API}/settings",
        headers=tenant["headers"],
        json={"settings": {"not_a_real_setting": "x", "low_stock_notifications": False}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "not_a_real_setting" not in body["settings"]
    assert body["settings"]["low_stock_notifications"] is False


def test_manager_can_read_but_not_write_settings(client, tenant):
    # Warehouse managers may view settings but not change them.
    manager = add_user(client, tenant, "warehouse_manager")
    read = client.get(f"{API}/settings", headers=manager["headers"])
    assert read.status_code == 200
    write = client.patch(
        f"{API}/settings",
        headers=manager["headers"],
        json={"name": "Nope"},
    )
    assert write.status_code == 403
    assert write.json()["code"] == "forbidden"


def test_viewer_cannot_read_settings(client, tenant):
    viewer = add_user(client, tenant, "viewer")
    resp = client.get(f"{API}/settings", headers=viewer["headers"])
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"


def test_anonymous_cannot_read_settings(client):
    resp = client.get(f"{API}/settings")
    assert resp.status_code == 401
