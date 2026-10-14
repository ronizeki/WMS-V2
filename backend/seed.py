"""Idempotent demonstration data for StockPilot WMS."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from auth import get_password_hash
from models import (
    ALL_PERMISSIONS,
    Product,
    ProductCategory,
    RoleCode,
    StockMovementType,
    SubscriptionPlan,
    Supplier,
    Customer,
    TenantStatus,
    User,
    UserStatus,
    Warehouse,
    WarehouseLocation,
    utcnow,
)
from services.inventory import post_movement
from services.rbac import ensure_platform_roles, resolve_roles
from services.tenants import provision_tenant
from store import Store

logger = logging.getLogger(__name__)

PLATFORM_ADMIN_EMAIL = "admin@stockpilot.io"
PLATFORM_ADMIN_PASSWORD = "Admin123!"
DEMO_OWNER_EMAIL = "owner@demowms.id"
DEMO_OWNER_PASSWORD = "Demo1234!"
DEMO_TENANT_CODE = "DEMO"
DEMO_TENANT_ID = "demo-tenant"

PLANS = [
    {"code": "free", "name": "Free", "price": 0, "max_users": 3, "max_warehouses": 1,
     "max_products": 100, "max_locations": 25, "storage_gb": 1, "api_calls_monthly": 1000,
     "features": ["basic_inventory", "single_warehouse"], "is_free": True, "trial_days": 0},
    {"code": "starter", "name": "Starter", "price": 499000, "max_users": 10, "max_warehouses": 1,
     "max_products": 2000, "max_locations": 250, "storage_gb": 10, "api_calls_monthly": 50000,
     "features": ["basic_inventory", "receiving", "picking", "packing", "reports"],
     "trial_days": 14},
    {"code": "growth", "name": "Growth", "price": 1499000, "max_users": 50, "max_warehouses": 5,
     "max_products": 25000, "max_locations": 2500, "storage_gb": 100, "api_calls_monthly": 500000,
     "features": ["advanced_inventory", "transfers", "cycle_count", "batch_tracking",
                  "api_access", "priority_support"], "trial_days": 14},
    {"code": "enterprise", "name": "Enterprise", "price": 4999000, "max_users": 500,
     "max_warehouses": 100, "max_products": 500000, "max_locations": 100000, "storage_gb": 1000,
     "api_calls_monthly": 10000000,
     "features": ["all"], "trial_days": 30},
]

CATEGORIES = ["Electronics", "Apparel", "Home & Living", "FMCG", "Spare Parts"]

PRODUCTS = [
    {"sku": "ELEC-001", "name": "Wireless Mouse", "category": "Electronics", "cost": 85000, "sell": 149000, "rp": 20, "rq": 60, "barcode": "8991001000011"},
    {"sku": "ELEC-002", "name": "Mechanical Keyboard", "category": "Electronics", "cost": 350000, "sell": 549000, "rp": 10, "rq": 30, "barcode": "8991001000028"},
    {"sku": "ELEC-003", "name": "USB-C Hub 7-in-1", "category": "Electronics", "cost": 175000, "sell": 299000, "rp": 15, "rq": 40, "barcode": "8991001000035"},
    {"sku": "APP-001", "name": "Cotton T-Shirt (M)", "category": "Apparel", "cost": 45000, "sell": 99000, "rp": 50, "rq": 150, "barcode": "8991001000042"},
    {"sku": "APP-002", "name": "Denim Jacket", "category": "Apparel", "cost": 210000, "sell": 379000, "rp": 12, "rq": 36, "barcode": "8991001000059"},
    {"sku": "HOME-001", "name": "Ceramic Dinner Plate", "category": "Home & Living", "cost": 32000, "sell": 65000, "rp": 40, "rq": 120, "barcode": "8991001000066"},
    {"sku": "HOME-002", "name": "Stainless Steel Pan", "category": "Home & Living", "cost": 125000, "sell": 219000, "rp": 10, "rq": 30, "barcode": "8991001000073"},
    {"sku": "FMCG-001", "name": "Instant Coffee 20s", "category": "FMCG", "cost": 22000, "sell": 38000, "rp": 100, "rq": 300, "barcode": "8991001000080"},
    {"sku": "FMCG-002", "name": "Bottled Water 600ml (24pk)", "category": "FMCG", "cost": 38000, "sell": 58000, "rp": 80, "rq": 240, "barcode": "8991001000097"},
    {"sku": "SPARE-001", "name": "Conveyor Belt Roller", "category": "Spare Parts", "cost": 78000, "sell": 135000, "rp": 8, "rq": 24, "barcode": "8991001000103"},
]


async def seed_plans(store: Store) -> None:
    for plan in PLANS:
        if await store.find_one("subscription_plans", {"code": plan["code"]}):
            continue
        doc = SubscriptionPlan(**plan).model_dump(mode="python")
        await store.insert_one("subscription_plans", doc)


async def seed_platform_admin(store: Store) -> None:
    await ensure_platform_roles(store)
    if await store.find_one("users", {"email": PLATFORM_ADMIN_EMAIL}):
        return
    role = await store.find_one("roles", {"code": RoleCode.PLATFORM_ADMIN.value, "tenant_id": None})
    user = User(
        tenant_id=None,
        email=PLATFORM_ADMIN_EMAIL,
        full_name="Platform Administrator",
        hashed_password=get_password_hash(PLATFORM_ADMIN_PASSWORD),
        status=UserStatus.ACTIVE,
        role_ids=[role["id"]] if role else [],
        role_codes=[RoleCode.PLATFORM_ADMIN.value],
        permissions=list(ALL_PERMISSIONS),
        is_platform_admin=True,
    )
    doc = user.model_dump(mode="python")
    await store.insert_one("users", doc)


async def seed_demo_tenant(store: Store) -> Optional[str]:
    existing = await store.find_one("tenants", {"code": DEMO_TENANT_CODE})
    if existing:
        return existing["id"]

    result = await provision_tenant(
        store,
        name="Demo Warehouse Indonesia",
        code=DEMO_TENANT_CODE,
        owner_email=DEMO_OWNER_EMAIL,
        owner_name="Demo Owner",
        owner_password=DEMO_OWNER_PASSWORD,
        plan_code="growth",
        is_demo=True,
        status=TenantStatus.ACTIVE,
    )
    tenant = result["tenant"]
    tenant_id = tenant["id"]

    # Additional demo users (one per role)
    extra_users = [
        ("manager@demowms.id", "Warehouse Manager", RoleCode.WAREHOUSE_MANAGER.value),
        ("supervisor@demowms.id", "Warehouse Supervisor", RoleCode.WAREHOUSE_SUPERVISOR.value),
        ("operator@demowms.id", "Warehouse Operator", RoleCode.WAREHOUSE_OPERATOR.value),
        ("viewer@demowms.id", "Auditor Viewer", RoleCode.VIEWER.value),
    ]
    for email, name, role_code in extra_users:
        role_ids, role_codes, permissions = await resolve_roles(
            store, tenant_id=tenant_id, role_codes=[role_code])
        user = User(
            tenant_id=tenant_id, email=email, full_name=name,
            hashed_password=get_password_hash("Demo1234!"), status=UserStatus.ACTIVE,
            role_ids=role_ids, role_codes=role_codes, permissions=permissions,
        )
        await store.insert_one("users", user.model_dump(mode="python"))

    # Warehouse + locations
    warehouse = Warehouse(tenant_id=tenant_id, code="MAIN", name="Main Distribution Center",
                          city="Jakarta", province="DKI Jakarta", is_default=True)
    wdoc = warehouse.model_dump(mode="python")
    await store.insert_one("warehouses", wdoc)

    locations = [
        ("RECV-01", "Receiving Dock", "receiving", False),
        ("STOR-A01", "Storage Aisle A-01", "storage", True),
        ("STOR-A02", "Storage Aisle A-02", "storage", True),
        ("STOR-B01", "Storage Aisle B-01", "storage", True),
        ("PICK-01", "Picking Face", "picking", True),
        ("SHIP-01", "Shipping Dock", "shipping", False),
        ("QUAR-01", "Quarantine", "quarantine", False),
    ]
    location_ids: Dict[str, str] = {}
    for code, name, ltype, pickable in locations:
        loc = WarehouseLocation(tenant_id=tenant_id, warehouse_id=wdoc["id"], code=code,
                               name=name, location_type=ltype, is_pickable=pickable)
        doc = loc.model_dump(mode="python")
        await store.insert_one("warehouse_locations", doc)
        location_ids[code] = doc["id"]

    # Categories
    category_ids: Dict[str, str] = {}
    for name in CATEGORIES:
        cat = ProductCategory(tenant_id=tenant_id, name=name, code=name[:3].upper())
        doc = cat.model_dump(mode="python")
        await store.insert_one("product_categories", doc)
        category_ids[name] = doc["id"]

    # Products
    product_docs: List[Dict[str, Any]] = []
    for spec in PRODUCTS:
        product = Product(
            tenant_id=tenant_id, sku=spec["sku"], name=spec["name"], barcode=spec["barcode"],
            category_id=category_ids.get(spec["category"]), brand="StockPilot Demo",
            cost_price=spec["cost"], selling_price=spec["sell"],
            reorder_point=spec["rp"], reorder_quantity=spec["rq"],
        )
        doc = product.model_dump(mode="python")
        await store.insert_one("products", doc)
        product_docs.append(doc)

    # Partners
    suppliers = [
        Supplier(tenant_id=tenant_id, code="SUP-001", name="PT Nusantara Elektronik",
                 contact_name="Budi Santoso", email="sales@nusantara-elektronik.id",
                 phone="+62215550001", city="Jakarta"),
        Supplier(tenant_id=tenant_id, code="SUP-002", name="CV Sumber Pangan Sejahtera",
                 contact_name="Siti Aminah", email="order@sumberpangan.co.id",
                 phone="+62215550002", city="Bandung"),
    ]
    for supplier in suppliers:
        await store.insert_one("suppliers", supplier.model_dump(mode="python"))

    customers = [
        Customer(tenant_id=tenant_id, code="CUS-001", name="PT Retail Maju Bersama",
                 contact_name="Andi Wijaya", email="purchasing@retailmaju.id",
                 phone="+62215550011", city="Jakarta"),
        Customer(tenant_id=tenant_id, code="CUS-002", name="Toko Online Berkah Jaya",
                 contact_name="Rina Melati", email="hello@berkahjaya.id",
                 phone="+62215550012", city="Surabaya"),
    ]
    for customer in customers:
        await store.insert_one("customers", customer.model_dump(mode="python"))

    # Initial stock: receive most products into storage
    storage_location = location_ids["STOR-A01"]
    for index, product in enumerate(product_docs):
        qty = 150 + index * 10
        if index % 4 == 0:
            qty = 12  # a couple of low-stock items
        await post_movement(
            store, tenant_id=tenant_id, warehouse_id=wdoc["id"], location_id=storage_location,
            product=product, movement_type=StockMovementType.INBOUND_RECEIPT, quantity=qty,
            unit_cost=float(product.get("cost_price") or 0),
            reference_type="seed", reference_number="SEED-OPENING",
            reason="Opening balance", notes="Auto-generated demo opening stock",
        )

    logger.info("Seeded demo tenant %s", tenant_id)
    return tenant_id


async def ensure_seed(store: Store, force: bool = False) -> Dict[str, Any]:
    await seed_plans(store)
    await seed_platform_admin(store)
    existing_tenants = await store.count("tenants", {})
    if existing_tenants and not force:
        return {"seeded": False, "reason": "data already present",
                "tenants": existing_tenants, "backend": store.backend_name}
    tenant_id = await seed_demo_tenant(store)
    return {"seeded": True, "demo_tenant_id": tenant_id, "backend": store.backend_name}
