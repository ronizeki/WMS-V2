"""Cycle counting / stocktake."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError, ValidationError
from models import (
    ApprovalStatus,
    CycleCount,
    CycleCountLine,
    CycleCountStatus,
    StockMovementType,
    utcnow,
)
from routers.common import paginated
from services.audit import record_audit
from services.idempotency import run_idempotent
from services.inventory import get_stock_position, post_movement
from services.numbering import next_number

router = APIRouter(prefix="/cycle-counts", tags=["stocktake"])


class CycleCountPayload(BaseModel):
    warehouse_id: str
    location_id: Optional[str] = None
    count_type: str = "location"  # location | products | full
    assigned_to: Optional[str] = None
    product_ids: List[str] = []
    notes: Optional[str] = None


class CountLinePayload(BaseModel):
    line_id: str
    counted_qty: float
    notes: Optional[str] = None


class CountPayload(BaseModel):
    lines: List[CountLinePayload] = []


@router.get("")
async def list_cycle_counts(ctx: Context = Depends(require_permission("stocktake:read")),
                            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                            status: Optional[CycleCountStatus] = None,
                            warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "cycle_counts", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("", status_code=201)
async def create_cycle_count(payload: CycleCountPayload,
                             ctx: Context = Depends(require_permission("stocktake:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if not await ctx.store.find_one("warehouses", ctx.scope({"id": payload.warehouse_id})):
        raise NotFoundError("Warehouse not found")

    balance_query = ctx.scope({"warehouse_id": payload.warehouse_id})
    if payload.location_id:
        balance_query["location_id"] = payload.location_id
    if payload.product_ids:
        balance_query["product_id"] = {"$in": payload.product_ids}

    balances = await ctx.store.find_many("inventory_balances", balance_query)
    if not balances:
        raise ValidationError("No stock found for the selected scope")

    lines = [
        CycleCountLine(
            product_id=balance["product_id"], sku=balance.get("sku"),
            product_name=balance.get("product_name"), location_id=balance["location_id"],
            location_code=balance.get("location_id"), system_qty=float(balance.get("quantity_on_hand") or 0),
            unit=balance.get("unit", "PCS"),
        )
        for balance in balances
    ]
    count = CycleCount(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "cycle_count"),
        warehouse_id=payload.warehouse_id, location_id=payload.location_id,
        count_type=payload.count_type, assigned_to=payload.assigned_to,
        notes=payload.notes, created_by=ctx.user_id, lines=lines,
        status=CycleCountStatus.DRAFT, approval_status=ApprovalStatus.PENDING.value,
    )
    doc = count.model_dump(mode="python")
    await ctx.store.insert_one("cycle_counts", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="cycle_count", entity_id=doc["id"],
                       description="Cycle count created", **ctx.client_meta())
    return doc


@router.get("/{count_id}")
async def get_cycle_count(count_id: str,
                          ctx: Context = Depends(require_permission("stocktake:read"))) -> Dict[str, Any]:
    count = await ctx.store.find_one("cycle_counts", ctx.scope({"id": count_id}))
    if not count:
        raise NotFoundError("Cycle count not found")
    return count


@router.post("/{count_id}/start")
async def start_cycle_count(count_id: str,
                            ctx: Context = Depends(require_permission("stocktake:write"))) -> Dict[str, Any]:
    count = await ctx.store.find_one("cycle_counts", ctx.scope({"id": count_id}))
    if not count:
        raise NotFoundError("Cycle count not found")
    await ctx.store.update_one("cycle_counts", ctx.scope({"id": count_id}),
                               set_fields={"status": CycleCountStatus.IN_PROGRESS.value,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("cycle_counts", {"id": count_id})


@router.post("/{count_id}/count")
async def submit_count(count_id: str, payload: CountPayload,
                       ctx: Context = Depends(require_permission("stocktake:write"))) -> Dict[str, Any]:
    count = await ctx.store.find_one("cycle_counts", ctx.scope({"id": count_id}))
    if not count:
        raise NotFoundError("Cycle count not found")
    if count.get("status") in (CycleCountStatus.APPROVED.value, CycleCountStatus.COMPLETED.value):
        raise ValidationError("This cycle count is already finalised")

    submitted = {line.line_id: line for line in payload.lines}
    updated = []
    for line in count.get("lines", []):
        if line["id"] in submitted:
            entry = submitted[line["id"]]
            variance = float(entry.counted_qty) - float(line.get("system_qty") or 0.0)
            updated.append({**line, "counted_qty": float(entry.counted_qty),
                            "variance_qty": variance, "counted": True,
                            "notes": entry.notes or line.get("notes")})
        else:
            updated.append(line)

    await ctx.store.update_one(
        "cycle_counts", ctx.scope({"id": count_id}),
        set_fields={"lines": updated, "status": CycleCountStatus.PENDING_APPROVAL.value,
                    "approval_status": ApprovalStatus.PENDING.value, "updated_at": utcnow()},
    )
    return await ctx.store.find_one("cycle_counts", {"id": count_id})


@router.post("/{count_id}/approve")
async def approve_cycle_count(count_id: str,
                              idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                              ctx: Context = Depends(require_permission("stocktake:approve"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    count = await ctx.store.find_one("cycle_counts", ctx.scope({"id": count_id}))
    if not count:
        raise NotFoundError("Cycle count not found")
    if count.get("posted"):
        return count

    async def _approve() -> Dict[str, Any]:
        settings = (await ctx.store.find_one("tenants", {"id": tenant_id}) or {}).get("settings") or {}
        allow_negative = bool(settings.get("allow_negative_stock"))
        adjustments = 0
        updated_lines = []
        for line in count.get("lines", []):
            system_qty = float(line.get("system_qty") or 0.0)
            if not line.get("counted"):
                updated_lines.append(line)
                continue
            counted = float(line.get("counted_qty") or 0.0)
            # Recompute against the live balance to avoid acting on stale data.
            current = await get_stock_position(ctx.store, tenant_id, count["warehouse_id"],
                                               line["product_id"], location_id=line["location_id"])
            variance = counted - current["on_hand"]
            if abs(variance) > 1e-6:
                product = await ctx.store.find_one("products", ctx.scope({"id": line["product_id"]}))
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=count["warehouse_id"],
                    location_id=line["location_id"], product=product,
                    movement_type=StockMovementType.CYCLE_COUNT_ADJUSTMENT, quantity=variance,
                    reference_type="cycle_count", reference_id=count["id"],
                    reference_number=count["number"], reason="cycle count variance",
                    notes=line.get("notes"), created_by=ctx.user_id, allow_negative=allow_negative,
                )
                adjustments += 1
            updated_lines.append({**line, "system_qty": current["on_hand"], "variance_qty": variance})

        await ctx.store.update_one(
            "cycle_counts", ctx.scope({"id": count_id}),
            set_fields={"lines": updated_lines, "status": CycleCountStatus.COMPLETED.value,
                        "approval_status": ApprovalStatus.APPROVED.value,
                        "approved_by": ctx.user_id, "approved_at": utcnow(),
                        "posted": True, "posted_at": utcnow(), "updated_at": utcnow()},
        )
        result = await ctx.store.find_one("cycle_counts", {"id": count_id})
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="approve",
                           entity_type="cycle_count", entity_id=count_id,
                           description=f"Cycle count approved ({adjustments} adjustments posted)",
                           **ctx.client_meta())
        return result

    return await run_idempotent(
        ctx.store, tenant_id=tenant_id, key=idempotency_key,
        endpoint=f"cycle_counts:{count_id}:approve",
        payload={"count_id": count_id}, handler=_approve,
    )


@router.post("/{count_id}/reject")
async def reject_cycle_count(count_id: str,
                             ctx: Context = Depends(require_permission("stocktake:approve"))) -> Dict[str, Any]:
    count = await ctx.store.find_one("cycle_counts", ctx.scope({"id": count_id}))
    if not count:
        raise NotFoundError("Cycle count not found")
    await ctx.store.update_one("cycle_counts", ctx.scope({"id": count_id}),
                               set_fields={"status": CycleCountStatus.REJECTED.value,
                                           "approval_status": ApprovalStatus.REJECTED.value,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("cycle_counts", {"id": count_id})
