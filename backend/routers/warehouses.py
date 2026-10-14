"""Warehouses, zones and locations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import ConflictError, NotFoundError, ValidationError
from models import (
    LocationStatus,
    LocationType,
    Warehouse,
    WarehouseLocation,
    WarehouseStatus,
    WarehouseZone,
    utcnow,
)
from routers.common import clean, get_or_404, paginated
from services.audit import record_audit

router = APIRouter(tags=["warehouses"])


class WarehousePayload(BaseModel):
    code: str
    name: str
    status: WarehouseStatus = WarehouseStatus.ACTIVE
    timezone: str = "Asia/Jakarta"
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "Indonesia"
    phone: Optional[str] = None
    manager_id: Optional[str] = None
    is_default: bool = False


class ZonePayload(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class LocationPayload(BaseModel):
    code: str
    name: Optional[str] = None
    zone_id: Optional[str] = None
    location_type: LocationType = LocationType.STORAGE
    status: LocationStatus = LocationStatus.AVAILABLE
    aisle: Optional[str] = None
    rack: Optional[str] = None
    shelf: Optional[str] = None
    bin: Optional[str] = None
    max_capacity: Optional[float] = None
    max_weight_kg: Optional[float] = None
    is_pickable: bool = True


@router.get("/warehouses")
async def list_warehouses(ctx: Context = Depends(require_permission("warehouse:read")),
                          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                          search: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"code": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "warehouses", query, page=page, page_size=page_size,
                           sort=[("created_at", 1)])


@router.post("/warehouses", status_code=201)
async def create_warehouse(payload: WarehousePayload,
                           ctx: Context = Depends(require_permission("warehouse:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if await ctx.store.find_one("warehouses", {"tenant_id": tenant_id, "code": payload.code.upper()}):
        raise ConflictError("A warehouse with this code already exists")
    warehouse = Warehouse(tenant_id=tenant_id, **payload.model_dump())
    warehouse.code = warehouse.code.upper()
    doc = warehouse.model_dump(mode="python")
    if payload.is_default:
        for existing in await ctx.store.find_many("warehouses", {"tenant_id": tenant_id}):
            if existing.get("is_default"):
                await ctx.store.update_one("warehouses", {"id": existing["id"]},
                                           set_fields={"is_default": False})
    await ctx.store.insert_one("warehouses", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="warehouse", entity_id=doc["id"], after=doc, **ctx.client_meta())
    return doc


@router.get("/warehouses/{warehouse_id}")
async def get_warehouse(warehouse_id: str,
                        ctx: Context = Depends(require_permission("warehouse:read"))) -> Dict[str, Any]:
    return await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)


@router.patch("/warehouses/{warehouse_id}")
async def update_warehouse(warehouse_id: str, payload: WarehousePayload,
                           ctx: Context = Depends(require_permission("warehouse:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    updates = clean(payload.model_dump())
    updates = {k: (v.value if hasattr(v, "value") else v) for k, v in updates.items()}
    updates["updated_at"] = utcnow()
    if updates.get("is_default"):
        for existing in await ctx.store.find_many("warehouses", {"tenant_id": tenant_id}):
            if existing.get("is_default") and existing["id"] != warehouse_id:
                await ctx.store.update_one("warehouses", {"id": existing["id"]},
                                           set_fields={"is_default": False})
    await ctx.store.update_one("warehouses", {"id": warehouse_id, "tenant_id": tenant_id},
                               set_fields=updates)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="update",
                       entity_type="warehouse", entity_id=warehouse_id, after=updates,
                       **ctx.client_meta())
    return await ctx.store.find_one("warehouses", {"id": warehouse_id})


@router.delete("/warehouses/{warehouse_id}", status_code=204)
async def delete_warehouse(warehouse_id: str,
                           ctx: Context = Depends(require_permission("warehouse:write"))) -> None:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    balance = await ctx.store.find_one("inventory_balances",
                                       {"tenant_id": tenant_id, "warehouse_id": warehouse_id,
                                        "quantity_on_hand": {"$gt": 0}})
    if balance:
        raise ValidationError("Cannot delete a warehouse that still holds stock")
    await ctx.store.update_one("warehouses", {"id": warehouse_id, "tenant_id": tenant_id},
                               set_fields={"status": WarehouseStatus.CLOSED.value, "updated_at": utcnow()})


@router.get("/warehouses/{warehouse_id}/zones")
async def list_zones(warehouse_id: str,
                     ctx: Context = Depends(require_permission("warehouse:read"))) -> Dict[str, Any]:
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    zones = await ctx.store.find_many("warehouse_zones",
                                      ctx.scope({"warehouse_id": warehouse_id}), sort=[("code", 1)])
    return {"items": zones}


@router.post("/warehouses/{warehouse_id}/zones", status_code=201)
async def create_zone(warehouse_id: str, payload: ZonePayload,
                      ctx: Context = Depends(require_permission("warehouse:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    zone = WarehouseZone(tenant_id=tenant_id, warehouse_id=warehouse_id, **payload.model_dump())
    doc = zone.model_dump(mode="python")
    await ctx.store.insert_one("warehouse_zones", doc)
    return doc


@router.get("/warehouses/{warehouse_id}/locations")
async def list_locations(warehouse_id: str,
                         ctx: Context = Depends(require_permission("warehouse:read")),
                         page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                         search: Optional[str] = None,
                         location_type: Optional[LocationType] = None) -> Dict[str, Any]:
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    query = ctx.scope({"warehouse_id": warehouse_id})
    if location_type:
        query["location_type"] = location_type.value
    if search:
        query["code"] = {"$regex": search, "$options": "i"}
    return await paginated(ctx.store, "warehouse_locations", query, page=page, page_size=page_size,
                           sort=[("code", 1)])


@router.post("/warehouses/{warehouse_id}/locations", status_code=201)
async def create_location(warehouse_id: str, payload: LocationPayload,
                          ctx: Context = Depends(require_permission("warehouse:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouses", ctx, warehouse_id)
    if await ctx.store.find_one("warehouse_locations",
                                {"tenant_id": tenant_id, "warehouse_id": warehouse_id,
                                 "code": payload.code.upper()}):
        raise ConflictError("A location with this code already exists in the warehouse")
    location = WarehouseLocation(tenant_id=tenant_id, warehouse_id=warehouse_id, **payload.model_dump())
    location.code = location.code.upper()
    doc = location.model_dump(mode="python")
    await ctx.store.insert_one("warehouse_locations", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="location", entity_id=doc["id"], after=doc, **ctx.client_meta())
    return doc


@router.patch("/locations/{location_id}")
async def update_location(location_id: str, payload: LocationPayload,
                          ctx: Context = Depends(require_permission("warehouse:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouse_locations", ctx, location_id)
    updates = clean(payload.model_dump())
    updates = {k: (v.value if hasattr(v, "value") else v) for k, v in updates.items()}
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("warehouse_locations", {"id": location_id, "tenant_id": tenant_id},
                               set_fields=updates)
    return await ctx.store.find_one("warehouse_locations", {"id": location_id})


@router.delete("/locations/{location_id}", status_code=204)
async def delete_location(location_id: str,
                          ctx: Context = Depends(require_permission("warehouse:write"))) -> None:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "warehouse_locations", ctx, location_id)
    balance = await ctx.store.find_one("inventory_balances",
                                       {"tenant_id": tenant_id, "location_id": location_id,
                                        "quantity_on_hand": {"$gt": 0}})
    if balance:
        raise ValidationError("Cannot delete a location that still holds stock")
    await ctx.store.delete_one("warehouse_locations", {"id": location_id, "tenant_id": tenant_id})
