"""Pytest fixtures.

The suite runs entirely against the in-memory storage backend so it is fast
and hermetic, while exercising the exact same service-layer code paths used in
production against MongoDB.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Configure the environment *before* importing the application.
os.environ.setdefault("SKIP_MONGO", "true")
os.environ.setdefault("DEMO_DATA_ENABLED", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-stockpilot-wms-min-32-bytes")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server import app  # noqa: E402
from store import get_store  # noqa: E402

API = "/api/v1"
PLATFORM_ADMIN = ("admin@stockpilot.io", "Admin123!")
OWNER_PASSWORD = "Owner1234!"

_counter = {"value": 0}


def unique(prefix: str) -> str:
    _counter["value"] += 1
    return f"{prefix}{_counter['value']}{uuid.uuid4().hex[:6]}"


def login(client: TestClient, email: str, password: str, tenant_code: str | None = None) -> str:
    payload = {"email": email, "password": password}
    if tenant_code:
        payload["tenant_code"] = tenant_code
    resp = client.post(f"{API}/auth/login", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def store():
    return get_store()


@pytest.fixture(scope="session")
def platform_headers(client):
    return auth_headers(login(client, *PLATFORM_ADMIN))


@pytest.fixture
def tenant(client, platform_headers):
    """Provision a brand-new tenant with an owner for each test."""
    code = unique("T").upper()
    email = f"owner-{code.lower()}@example.com"
    resp = client.post(
        f"{API}/platform/tenants",
        headers=platform_headers,
        json={
            "name": f"Test Tenant {code}",
            "code": code,
            "owner_email": email,
            "owner_name": "Test Owner",
            "owner_password": OWNER_PASSWORD,
            "plan_code": "growth",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    token = login(client, email, OWNER_PASSWORD, tenant_code=code)
    return {
        "id": data["tenant"]["id"],
        "code": code,
        "owner_email": email,
        "owner_token": token,
        "headers": auth_headers(token),
    }


def add_user(client, tenant, role_code: str, password: str = "User1234!") -> dict:
    email = f"{role_code}-{tenant['code'].lower()}@example.com"
    resp = client.post(
        f"{API}/users",
        headers=tenant["headers"],
        json={
            "email": email,
            "full_name": role_code.replace("_", " ").title(),
            "password": password,
            "role_codes": [role_code],
        },
    )
    assert resp.status_code == 201, resp.text
    token = login(client, email, password, tenant_code=tenant["code"])
    return {"email": email, "id": resp.json()["id"], "token": token, "headers": auth_headers(token)}


@pytest.fixture
def warehouse(client, tenant):
    resp = client.post(
        f"{API}/warehouses",
        headers=tenant["headers"],
        json={"code": "MAIN", "name": "Main Warehouse", "is_default": True},
    )
    assert resp.status_code == 201, resp.text
    warehouse = resp.json()

    locations = {}
    for code, ltype, pickable in (
        ("RECV-01", "receiving", False),
        ("STOR-A01", "storage", True),
        ("STOR-A02", "storage", True),
        ("SHIP-01", "shipping", False),
    ):
        location = client.post(
            f"{API}/warehouses/{warehouse['id']}/locations",
            headers=tenant["headers"],
            json={"code": code, "location_type": ltype, "is_pickable": pickable},
        )
        assert location.status_code == 201, location.text
        locations[code] = location.json()["id"]

    return {"warehouse": warehouse, "locations": locations}


@pytest.fixture
def product_factory(client, tenant):
    def make(sku: str, reorder_point: float = 0.0, **kwargs):
        payload = {
            "sku": sku,
            "name": f"Product {sku}",
            "cost_price": 100.0,
            "selling_price": 200.0,
            "reorder_point": reorder_point,
            **kwargs,
        }
        resp = client.post(f"{API}/products", headers=tenant["headers"], json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return make


def receive_stock(client, tenant, warehouse, product, quantity, location_code="STOR-A01", unit_cost=100.0):
    """Receive stock directly through the goods-receipt posting flow."""
    resp = client.post(
        f"{API}/goods-receipts",
        headers=tenant["headers"],
        json={
            "warehouse_id": warehouse["warehouse"]["id"],
            "lines": [{
                "product_id": product["id"],
                "received_qty": quantity,
                "unit_cost": unit_cost,
                "receiving_location_id": warehouse["locations"][location_code],
            }],
        },
    )
    assert resp.status_code == 201, resp.text
    receipt = resp.json()
    posted = client.post(f"{API}/goods-receipts/{receipt['id']}/post", headers=tenant["headers"])
    assert posted.status_code == 200, posted.text
    return posted.json()
