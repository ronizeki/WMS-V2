"""Multi-tenant isolation: no cross-tenant reads or writes (IDOR protection)."""
from __future__ import annotations

from tests.conftest import API, login


def _make_tenant_with_warehouse(client, platform_headers, label):
    resp = client.post(
        f"{API}/platform/tenants",
        headers=platform_headers,
        json={"name": f"Tenant {label}", "code": f"ISO{label}",
              "owner_email": f"owner{label}@example.com", "owner_name": "Owner",
              "owner_password": "Owner1234!", "plan_code": "starter"},
    )
    assert resp.status_code == 201, resp.text
    tenant = resp.json()["tenant"]
    token = login(client, f"owner{label}@example.com", "Owner1234!", tenant_code=f"ISO{label}")
    headers = {"Authorization": f"Bearer {token}"}
    warehouse = client.post(f"{API}/warehouses", headers=headers,
                            json={"code": "WH", "name": f"WH {label}"})
    assert warehouse.status_code == 201, warehouse.text
    return tenant, headers, warehouse.json()


def test_cross_tenant_read_is_blocked(client, platform_headers):
    tenant_a, headers_a, warehouse_a = _make_tenant_with_warehouse(client, platform_headers, "A")
    tenant_b, headers_b, warehouse_b = _make_tenant_with_warehouse(client, platform_headers, "B")

    # Tenant A cannot see tenant B's warehouse, even with the exact id
    resp = client.get(f"{API}/warehouses/{warehouse_b['id']}", headers=headers_a)
    assert resp.status_code == 404

    # Listing only ever returns the caller's own data
    listing = client.get(f"{API}/warehouses", headers=headers_a)
    assert listing.status_code == 200
    ids = [w["id"] for w in listing.json()["items"]]
    assert warehouse_a["id"] in ids
    assert warehouse_b["id"] not in ids


def test_cross_tenant_write_is_blocked(client, platform_headers):
    _tenant_a, headers_a, _warehouse_a = _make_tenant_with_warehouse(client, platform_headers, "C")
    tenant_b, _headers_b, warehouse_b = _make_tenant_with_warehouse(client, platform_headers, "D")

    # Attempting to mutate another tenant's warehouse must not succeed
    resp = client.patch(f"{API}/warehouses/{warehouse_b['id']}", headers=headers_a,
                        json={"code": "PWNED", "name": "Hijacked"})
    assert resp.status_code == 404

    # Confirm the record is untouched for its real owner
    check = client.get(f"{API}/warehouses/{warehouse_b['id']}", headers=headers_a)
    assert check.status_code == 404
    b_headers = {"Authorization": f"Bearer {login(client, 'ownerD@example.com', 'Owner1234!', tenant_code='ISOD')}"}
    check_b = client.get(f"{API}/warehouses/{warehouse_b['id']}", headers=b_headers)
    assert check_b.status_code == 200
    assert check_b.json()["code"] == "WH"


def test_tenant_user_cannot_impersonate_another_tenant(client, platform_headers):
    tenant_a, headers_a, _ = _make_tenant_with_warehouse(client, platform_headers, "E")
    tenant_b, _headers_b, _ = _make_tenant_with_warehouse(client, platform_headers, "F")

    resp = client.get(f"{API}/warehouses",
                      headers={**headers_a, "X-Tenant-Id": tenant_b["id"]})
    assert resp.status_code == 403
    assert resp.json()["code"] == "forbidden"


def test_users_are_scoped_to_tenant(client, platform_headers):
    tenant_a, headers_a, _ = _make_tenant_with_warehouse(client, platform_headers, "G")
    tenant_b, headers_b, _ = _make_tenant_with_warehouse(client, platform_headers, "H")

    a_users = client.get(f"{API}/users", headers=headers_a).json()
    b_users = client.get(f"{API}/users", headers=headers_b).json()
    a_emails = {u["email"] for u in a_users["items"]}
    b_emails = {u["email"] for u in b_users["items"]}
    assert a_emails.isdisjoint(b_emails)
    assert all(u["tenant_id"] == tenant_a["id"] for u in a_users["items"])
    assert all(u["tenant_id"] == tenant_b["id"] for u in b_users["items"])
