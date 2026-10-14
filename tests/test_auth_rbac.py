"""Authentication, authorization and RBAC enforcement."""
from __future__ import annotations

from tests.conftest import API, PLATFORM_ADMIN, add_user, auth_headers, login


def test_health_reports_storage_backend(client):
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["storage_backend"] == "memory"


def test_login_rejects_bad_password(client, tenant):
    resp = client.post(f"{API}/auth/login",
                       json={"email": tenant["owner_email"], "password": "wrong-password",
                             "tenant_code": tenant["code"]})
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


def test_me_returns_tenant_context(client, tenant):
    resp = client.get(f"{API}/auth/me", headers=tenant["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == tenant["owner_email"]
    assert body["tenant"]["id"] == tenant["id"]
    assert "hashed_password" not in body


def test_requires_authentication(client):
    resp = client.get(f"{API}/warehouses")
    assert resp.status_code == 401


def test_viewer_cannot_adjust_stock(client, tenant, warehouse, product_factory):
    viewer = add_user(client, tenant, "viewer")
    product = product_factory("VIEW-1")
    resp = client.post(
        f"{API}/inventory/adjustments",
        headers=viewer["headers"],
        json={
            "warehouse_id": warehouse["warehouse"]["id"],
            "location_id": warehouse["locations"]["STOR-A01"],
            "product_id": product["id"],
            "adjustment_type": "increase",
            "quantity": 5,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"
    assert "inventory:adjust" in resp.json()["details"]["missing_permissions"]


def test_operator_cannot_manage_products(client, tenant):
    operator = add_user(client, tenant, "warehouse_operator")
    resp = client.post(f"{API}/products", headers=operator["headers"],
                       json={"sku": "OP-1", "name": "Should fail"})
    assert resp.status_code == 403


def test_operator_can_read_inventory(client, tenant, warehouse, product_factory):
    operator = add_user(client, tenant, "warehouse_operator")
    product_factory("OP-2")
    resp = client.get(f"{API}/inventory/balances", headers=operator["headers"])
    assert resp.status_code == 200


def test_warehouse_manager_can_create_products(client, tenant):
    manager = add_user(client, tenant, "warehouse_manager")
    resp = client.post(f"{API}/products", headers=manager["headers"],
                       json={"sku": "MGR-1", "name": "Manager Product"})
    assert resp.status_code == 201


def test_platform_admin_needs_tenant_header(client, tenant, warehouse):
    platform = auth_headers(login(client, *PLATFORM_ADMIN))
    # No tenant selected -> cannot act on tenant-scoped data
    resp = client.get(f"{API}/warehouses", headers=platform)
    assert resp.status_code == 422

    # With an explicit tenant header the platform admin can act
    resp = client.get(f"{API}/warehouses", headers={**platform, "X-Tenant-Id": tenant["id"]})
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1


def test_permission_catalog_is_exposed(client, tenant):
    resp = client.get(f"{API}/permissions", headers=tenant["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert any(p["code"] == "inventory:adjust" for p in body["permissions"])
    assert "inventory" in body["by_category"]
