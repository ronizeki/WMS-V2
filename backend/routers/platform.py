"""Platform administration: tenants, plans and cross-tenant stats."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from deps import Context, get_context, require_permission
from errors import NotFoundError, ValidationError
from models import SubscriptionPlan, TenantCreate, TenantStatus
from routers.common import clean, paginated
from serializers import public
from services.audit import record_audit
from services.rbac import ensure_platform_roles
from services.tenants import provision_tenant
from store import get_store

router = APIRouter(prefix="/platform", tags=["platform"])


class TenantUpdatePayload(BaseModel):
    name: Optional[str] = None
    status: Optional[TenantStatus] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    locale: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class PlanPayload(BaseModel):
    name: str
    code: str
    price: float = 0.0
    billing_cycle: str = "monthly"
    max_users: int = 10
    max_warehouses: int = 1
    max_products: int = 1000
    max_locations: int = 100
    storage_gb: int = 10
    api_calls_monthly: int = 10000
    features: List[str] = []
    is_free: bool = False
    trial_days: int = 14
    description: Optional[str] = None


@router.post("/tenants", status_code=201)
async def create_tenant(payload: TenantCreate,
                        ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    result = await provision_tenant(
        ctx.store,
        name=payload.name, code=payload.code,
        owner_email=payload.owner_email, owner_name=payload.owner_name,
        owner_password=payload.owner_password, plan_code=payload.plan_code,
        timezone_name=payload.timezone, currency=payload.currency,
    )
    await record_audit(
        ctx.store, tenant_id=result["tenant"]["id"], user=ctx.user,
        action="create", entity_type="tenant", entity_id=result["tenant"]["id"],
        description=f"Provisioned tenant {payload.code}",
        after={"name": payload.name, "code": payload.code},
        **ctx.client_meta(),
    )
    return {
        "tenant": public(result["tenant"]),
        "owner": public(result["owner"]),
        "subscription": result["subscription"],
    }


@router.get("/tenants")
async def list_tenants(ctx: Context = Depends(require_permission("tenant:manage")),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       search: Optional[str] = None,
                       status: Optional[TenantStatus] = None) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status.value
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    result = await paginated(ctx.store, "tenants", query, page=page, page_size=page_size,
                             sort=[("created_at", -1)])
    for item in result["items"]:
        item["user_count"] = await ctx.store.count("users", {"tenant_id": item["id"]})
        item["warehouse_count"] = await ctx.store.count("warehouses", {"tenant_id": item["id"]})
    return result


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str,
                     ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    tenant = await ctx.store.find_one("tenants", {"id": tenant_id})
    if not tenant:
        raise NotFoundError("Tenant not found")
    subscription = await ctx.store.find_one("subscriptions", {"tenant_id": tenant_id})
    return {
        "tenant": public(tenant),
        "subscription": subscription,
        "counts": {
            "users": await ctx.store.count("users", {"tenant_id": tenant_id}),
            "warehouses": await ctx.store.count("warehouses", {"tenant_id": tenant_id}),
            "products": await ctx.store.count("products", {"tenant_id": tenant_id}),
        },
    }


@router.patch("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, payload: TenantUpdatePayload,
                        ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    tenant = await ctx.store.find_one("tenants", {"id": tenant_id})
    if not tenant:
        raise NotFoundError("Tenant not found")
    updates = clean(payload.model_dump())
    if "status" in updates and hasattr(updates["status"], "value"):
        updates["status"] = updates["status"].value
    if "settings" in updates:
        merged = dict(tenant.get("settings") or {})
        merged.update(updates["settings"])
        updates["settings"] = merged
    from models import utcnow
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("tenants", {"id": tenant_id}, set_fields=updates)
    updated = await ctx.store.find_one("tenants", {"id": tenant_id})
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="update",
                       entity_type="tenant", entity_id=tenant_id,
                       before={"status": tenant.get("status")}, after=updates, **ctx.client_meta())
    return public(updated)


@router.get("/plans")
async def list_plans(ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    plans = await ctx.store.find_many("subscription_plans", {}, sort=[("price", 1)])
    return {"items": plans}


@router.post("/plans", status_code=201)
async def create_plan(payload: PlanPayload,
                      ctx: Context = Depends(require_permission("plan:manage"))) -> Dict[str, Any]:
    plan = SubscriptionPlan(**payload.model_dump())
    doc = plan.model_dump(mode="python")
    await ctx.store.insert_one("subscription_plans", doc)
    return doc


@router.patch("/plans/{plan_id}")
async def update_plan(plan_id: str, payload: PlanPayload,
                      ctx: Context = Depends(require_permission("plan:manage"))) -> Dict[str, Any]:
    plan = await ctx.store.find_one("subscription_plans", {"id": plan_id})
    if not plan:
        raise NotFoundError("Plan not found")
    updates = clean(payload.model_dump())
    await ctx.store.update_one("subscription_plans", {"id": plan_id}, set_fields=updates)
    return await ctx.store.find_one("subscription_plans", {"id": plan_id})


@router.get("/stats")
async def platform_stats(ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    store = ctx.store
    tenants = await store.find_many("tenants", {})
    by_status: Dict[str, int] = {}
    for tenant in tenants:
        key = tenant.get("status", "unknown")
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "tenants": {
            "total": len(tenants),
            "by_status": by_status,
            "demo": sum(1 for t in tenants if t.get("is_demo")),
        },
        "users": await store.count("users", {}),
        "warehouses": await store.count("warehouses", {}),
        "products": await store.count("products", {}),
        "ledger_entries": await store.count("stock_ledger", {}),
        "storage_backend": store.backend_name,
    }


@router.get("/bootstrap")
async def bootstrap(ctx: Context = Depends(require_permission("tenant:manage"))) -> Dict[str, Any]:
    """Idempotently ensure global platform roles/plan catalog exist."""
    await ensure_platform_roles(ctx.store)
    existing = await ctx.store.count("subscription_plans", {})
    return {"platform_roles_ready": True, "plans": existing}
