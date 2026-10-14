"""Tenant self-service settings and profile."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError
from models import TenantSettings, utcnow
from serializers import public
from services.audit import record_audit

router = APIRouter(prefix="/settings", tags=["settings"])

PROFILE_FIELDS = (
    "name", "timezone", "currency", "locale", "phone", "email", "address",
    "city", "province", "postal_code", "country", "website", "tax_number",
)


class SettingsPayload(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    locale: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    tax_number: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


async def _current_tenant(ctx: Context) -> Dict[str, Any]:
    tenant = await ctx.store.find_one("tenants", {"id": ctx.require_tenant()})
    if not tenant:
        raise NotFoundError("Tenant not found")
    return tenant


@router.get("")
async def get_settings(ctx: Context = Depends(require_permission("settings:read"))) -> Dict[str, Any]:
    tenant = await _current_tenant(ctx)
    defaults = TenantSettings().model_dump()
    merged = {**defaults, **(tenant.get("settings") or {})}
    return {**public(tenant), "settings": merged}


@router.patch("")
async def update_settings(payload: SettingsPayload,
                          ctx: Context = Depends(require_permission("settings:write"))) -> Dict[str, Any]:
    tenant = await _current_tenant(ctx)
    data = payload.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {}

    for field in PROFILE_FIELDS:
        if field in data and data[field] is not None:
            updates[field] = data[field]

    if data.get("settings"):
        current = {**TenantSettings().model_dump(), **(tenant.get("settings") or {})}
        allowed = set(TenantSettings().model_dump().keys())
        for key, value in data["settings"].items():
            if key in allowed:
                current[key] = value
        updates["settings"] = current

    if updates:
        updates["updated_at"] = utcnow()
        await ctx.store.update_one("tenants", {"id": tenant["id"]}, set_fields=updates)
        await record_audit(ctx.store, tenant_id=tenant["id"], user=ctx.user, action="update",
                           entity_type="tenant_settings", entity_id=tenant["id"], after=updates,
                           **ctx.client_meta())

    updated = await ctx.store.find_one("tenants", {"id": tenant["id"]})
    return {**public(updated), "settings": {**TenantSettings().model_dump(), **(updated.get("settings") or {})}}
