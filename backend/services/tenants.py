"""Tenant provisioning: create tenant, roles, owner and subscription."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from auth import get_password_hash
from errors import ConflictError
from models import (
    RoleCode,
    Subscription,
    SubscriptionStatus,
    Tenant,
    TenantStatus,
    User,
    UserStatus,
)
from services.rbac import ensure_tenant_roles, resolve_roles
from store import Store


async def get_plan(store: Store, plan_code: str) -> Optional[Dict[str, Any]]:
    return await store.find_one("subscription_plans", {"code": plan_code})


async def provision_tenant(
    store: Store,
    *,
    name: str,
    code: str,
    owner_email: str,
    owner_name: str,
    owner_password: str,
    plan_code: str = "starter",
    timezone_name: str = "Asia/Jakarta",
    currency: str = "IDR",
    locale: str = "id_ID",
    is_demo: bool = False,
    status: TenantStatus = TenantStatus.ACTIVE,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    code = code.strip().upper()
    if await store.find_one("tenants", {"code": code}):
        raise ConflictError(f"Tenant code '{code}' is already in use")

    tenant = Tenant(
        name=name, code=code, status=status, timezone=timezone_name,
        currency=currency, locale=locale, is_demo=is_demo, email=owner_email,
    )
    if settings:
        merged = tenant.settings.model_dump()
        merged.update({k: v for k, v in settings.items() if k in merged})
        tenant.settings = tenant.settings.model_copy(update=merged)

    tenant_doc = tenant.model_dump(mode="python")
    await store.insert_one("tenants", tenant_doc)

    await ensure_tenant_roles(store, tenant.id)
    role_ids, role_codes, permissions = await resolve_roles(
        store, tenant_id=tenant.id, role_codes=[RoleCode.TENANT_OWNER.value]
    )

    owner = User(
        tenant_id=tenant.id,
        email=owner_email.lower(),
        full_name=owner_name,
        hashed_password=get_password_hash(owner_password),
        status=UserStatus.ACTIVE,
        role_ids=role_ids,
        role_codes=role_codes,
        permissions=permissions,
        is_platform_admin=False,
    )
    owner_doc = owner.model_dump(mode="python")
    await store.insert_one("users", owner_doc)

    plan = await get_plan(store, plan_code)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan["id"] if plan else plan_code,
        status=SubscriptionStatus.TRIAL if (plan and plan.get("trial_days", 0) > 0) else SubscriptionStatus.ACTIVE,
        start_date=now,
        trial_end_date=(now + timedelta(days=plan.get("trial_days", 14))) if plan else None,
        next_billing_date=now + timedelta(days=30),
        amount=float(plan.get("price", 0.0)) if plan else 0.0,
        currency=currency,
    )
    await store.insert_one("subscriptions", subscription.model_dump(mode="python"))

    return {
        "tenant": tenant_doc,
        "owner": owner_doc,
        "subscription": subscription.model_dump(mode="python"),
    }
