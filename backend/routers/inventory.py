"""Inventory: balances, ledger, stock adjustments."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError, ValidationError
from models import (
    AdjustmentReason,
    ApprovalStatus,
    StockAdjustment,
    StockMovementType,
    utcnow,
)
from routers.common import clean, paginated
from services.audit import record_audit
from services.inventory import get_stock_position, post_movement
from services.numbering import next_number

router = APIRouter(prefix="/inventory", tags=["inventory"])


class AdjustmentPayload(BaseModel):
    warehouse_id: str
    location_id: str
    product_id: str
    adjustment_type: str = "increase"  # increase | decrease | set
    quantity: float
    unit_cost: float = 0.0
    reason: AdjustmentReason = AdjustmentReason.OTHER
    reason_notes: Optional[str] = None


async def _tenant_settings(ctx: Context) -> Dict[str, Any]:
    tenant = await ctx.store.find_one("tenants", {"id": ctx.require_tenant()})
    return (tenant or {}).get("settings") or {}


async def _load_product(ctx: Context, product_id: str) -> Dict[str, Any]:
    product = await ctx.store.find_one("products", ctx.scope({"id": product_id}))
    if not product:
        raise NotFoundError("Product not found")
    return product


async def _validate_location(ctx: Context, warehouse_id: str, location_id: str) -> Dict[str, Any]:
    location = await ctx.store.find_one(
        "warehouse_locations", ctx.scope({"id": location_id, "warehouse_id": warehouse_id}))
    if not location:
        raise NotFoundError("Location not found in the selected warehouse")
    return location


@router.get("/balances")
async def list_balances(ctx: Context = Depends(require_permission("inventory:read")),
                        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                        warehouse_id: Optional[str] = None,
                        location_id: Optional[str] = None,
                        product_id: Optional[str] = None,
                        search: Optional[str] = None,
                        only_available: bool = False,
                        include_zero: bool = False) -> Dict[str, Any]:
    query = ctx.scope()
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if location_id:
        query["location_id"] = location_id
    if product_id:
        query["product_id"] = product_id
    if only_available:
        query["quantity_available"] = {"$gt": 0}
    elif not include_zero:
        query["quantity_on_hand"] = {"$ne": 0}
    if search:
        query["$or"] = [
            {"sku": {"$regex": search, "$options": "i"}},
            {"product_name": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "inventory_balances", query, page=page, page_size=page_size,
                           sort=[("product_name", 1), ("location_id", 1)])


@router.get("/summary")
async def inventory_summary(ctx: Context = Depends(require_permission("inventory:read")),
                            warehouse_id: Optional[str] = None,
                            search: Optional[str] = None,
                            low_stock_only: bool = False,
                            page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """Product-level aggregation across locations (and optionally warehouses)."""
    query = ctx.scope()
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    balances = await ctx.store.find_many("inventory_balances", query)
    products = {p["id"]: p for p in await ctx.store.find_many("products", ctx.scope())}

    aggregate: Dict[str, Dict[str, Any]] = {}
    for balance in balances:
        pid = balance["product_id"]
        bucket = aggregate.setdefault(pid, {
            "product_id": pid,
            "sku": balance.get("sku"),
            "product_name": balance.get("product_name"),
            "unit": balance.get("unit"),
            "on_hand": 0.0, "reserved": 0.0, "available": 0.0,
            "damaged": 0.0, "quarantine": 0.0, "value": 0.0,
        })
        bucket["on_hand"] += float(balance.get("quantity_on_hand") or 0.0)
        bucket["reserved"] += float(balance.get("quantity_reserved") or 0.0)
        bucket["available"] += float(balance.get("quantity_available") or 0.0)
        bucket["damaged"] += float(balance.get("quantity_damaged") or 0.0)
        bucket["quarantine"] += float(balance.get("quantity_quarantine") or 0.0)
        bucket["value"] += float(balance.get("total_value") or 0.0)

    items = []
    for bucket in aggregate.values():
        product = products.get(bucket["product_id"], {})
        bucket["reorder_point"] = float(product.get("reorder_point") or 0.0)
        bucket["reorder_quantity"] = float(product.get("reorder_quantity") or 0.0)
        bucket["is_low_stock"] = bucket["available"] < bucket["reorder_point"]
        bucket = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in bucket.items()}
        if search:
            haystack = f"{bucket.get('sku') or ''} {bucket.get('product_name') or ''}".lower()
            if search.lower() not in haystack:
                continue
        if low_stock_only and not bucket["is_low_stock"]:
            continue
        items.append(bucket)

    items.sort(key=lambda x: (x.get("product_name") or ""))
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "meta": {"page": page, "page_size": page_size, "total": total,
                 "total_pages": (total + page_size - 1) // page_size},
    }


@router.get("/position")
async def stock_position(warehouse_id: str, product_id: str,
                         location_id: Optional[str] = None,
                         ctx: Context = Depends(require_permission("inventory:read"))) -> Dict[str, Any]:
    return await get_stock_position(ctx.store, ctx.require_tenant(), warehouse_id, product_id,
                                    location_id=location_id)


@router.get("/ledger")
async def list_ledger(ctx: Context = Depends(require_permission("inventory:read")),
                      page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                      warehouse_id: Optional[str] = None,
                      product_id: Optional[str] = None,
                      movement_type: Optional[StockMovementType] = None,
                      reference_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if product_id:
        query["product_id"] = product_id
    if movement_type:
        query["movement_type"] = movement_type.value
    if reference_id:
        query["reference_id"] = reference_id
    return await paginated(ctx.store, "stock_ledger", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.get("/adjustments")
async def list_adjustments(ctx: Context = Depends(require_permission("inventory:read")),
                           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                           status: Optional[str] = None,
                           warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "stock_adjustments", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


async def _post_adjustment(ctx: Context, adjustment: Dict[str, Any]) -> Dict[str, Any]:
    product = await _load_product(ctx, adjustment["product_id"])
    signed = float(adjustment["quantity"])
    if adjustment.get("adjustment_type") == "decrease":
        signed = -abs(signed)
    elif adjustment.get("adjustment_type") == "set":
        position = await get_stock_position(ctx.store, adjustment["tenant_id"],
                                            adjustment["warehouse_id"], adjustment["product_id"],
                                            location_id=adjustment["location_id"])
        signed = float(adjustment["quantity"]) - position["on_hand"]
    else:
        signed = abs(signed)

    settings = await _tenant_settings(ctx)
    ledger, balance = await post_movement(
        ctx.store,
        tenant_id=adjustment["tenant_id"],
        warehouse_id=adjustment["warehouse_id"],
        location_id=adjustment["location_id"],
        product=product,
        movement_type=StockMovementType.ADJUSTMENT_IN if signed >= 0 else StockMovementType.ADJUSTMENT_OUT,
        quantity=signed,
        unit_cost=float(adjustment.get("unit_cost") or 0.0),
        reference_type="stock_adjustment",
        reference_id=adjustment["id"],
        reference_number=adjustment["number"],
        reason=str(adjustment.get("reason")),
        notes=adjustment.get("reason_notes"),
        created_by=ctx.user_id,
        allow_negative=bool(settings.get("allow_negative_stock")),
    )
    await ctx.store.update_one(
        "stock_adjustments", {"id": adjustment["id"], "tenant_id": adjustment["tenant_id"]},
        set_fields={
            "status": "posted",
            "posted": True,
            "posted_at": utcnow(),
            "approval_status": ApprovalStatus.APPROVED.value,
            "approved_by": ctx.user_id,
            "approved_at": utcnow(),
            "ledger_entry_id": ledger.get("id"),
            "updated_at": utcnow(),
        },
    )
    return await ctx.store.find_one("stock_adjustments", {"id": adjustment["id"]})


@router.post("/adjustments", status_code=201)
async def create_adjustment(payload: AdjustmentPayload,
                            ctx: Context = Depends(require_permission("inventory:adjust"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    product = await _load_product(ctx, payload.product_id)
    await _validate_location(ctx, payload.warehouse_id, payload.location_id)
    if payload.quantity < 0:
        raise ValidationError("Quantity must be a positive number")
    if payload.adjustment_type not in ("increase", "decrease", "set"):
        raise ValidationError("adjustment_type must be increase, decrease or set")

    settings = await _tenant_settings(ctx)
    requires_approval = bool(settings.get("require_adjustment_approval"))

    adjustment = StockAdjustment(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "adjustment"),
        warehouse_id=payload.warehouse_id,
        location_id=payload.location_id,
        product_id=payload.product_id,
        sku=product.get("sku"),
        product_name=product.get("name"),
        adjustment_type=payload.adjustment_type,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        reason=payload.reason,
        reason_notes=payload.reason_notes,
        status="pending_approval" if requires_approval else "draft",
        approval_status=ApprovalStatus.PENDING.value if requires_approval else ApprovalStatus.NOT_REQUIRED.value,
        created_by=ctx.user_id,
    )
    doc = adjustment.model_dump(mode="python")
    await ctx.store.insert_one("stock_adjustments", doc)

    if requires_approval:
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                           entity_type="stock_adjustment", entity_id=doc["id"], after=doc,
                           **ctx.client_meta())
        return doc

    posted = await _post_adjustment(ctx, doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="adjust_stock",
                       entity_type="stock_adjustment", entity_id=doc["id"], after=posted,
                       **ctx.client_meta())
    return posted


@router.post("/adjustments/{adjustment_id}/approve")
async def approve_adjustment(adjustment_id: str,
                             ctx: Context = Depends(require_permission("inventory:approve"))) -> Dict[str, Any]:
    adjustment = await ctx.store.find_one("stock_adjustments", ctx.scope({"id": adjustment_id}))
    if not adjustment:
        raise NotFoundError("Adjustment not found")
    if adjustment.get("posted"):
        raise ValidationError("This adjustment has already been posted")
    posted = await _post_adjustment(ctx, adjustment)
    await record_audit(ctx.store, tenant_id=ctx.require_tenant(), user=ctx.user, action="approve",
                       entity_type="stock_adjustment", entity_id=adjustment_id, after=posted,
                       **ctx.client_meta())
    return posted


@router.post("/adjustments/{adjustment_id}/reject")
async def reject_adjustment(adjustment_id: str, payload: Optional[Dict[str, str]] = None,
                            ctx: Context = Depends(require_permission("inventory:approve"))) -> Dict[str, Any]:
    adjustment = await ctx.store.find_one("stock_adjustments", ctx.scope({"id": adjustment_id}))
    if not adjustment:
        raise NotFoundError("Adjustment not found")
    if adjustment.get("posted"):
        raise ValidationError("This adjustment has already been posted")
    await ctx.store.update_one(
        "stock_adjustments", ctx.scope({"id": adjustment_id}),
        set_fields={
            "status": "rejected",
            "approval_status": ApprovalStatus.REJECTED.value,
            "rejection_reason": (payload or {}).get("reason"),
            "approved_by": ctx.user_id,
            "approved_at": utcnow(),
            "updated_at": utcnow(),
        },
    )
    return await ctx.store.find_one("stock_adjustments", {"id": adjustment_id})
