"""Stock transfers between warehouses/locations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError, ValidationError
from models import (
    ApprovalStatus,
    StockMovementType,
    StockTransfer,
    StockTransferLine,
    TransferStatus,
    utcnow,
)
from routers.common import paginated
from services.audit import record_audit
from services.idempotency import run_idempotent
from services.inventory import post_movement
from services.numbering import next_number

router = APIRouter(prefix="/transfers", tags=["transfers"])


class TransferLinePayload(BaseModel):
    product_id: str
    requested_qty: float
    unit: str = "PCS"
    batch_number: Optional[str] = None
    notes: Optional[str] = None


class TransferPayload(BaseModel):
    from_warehouse_id: str
    from_location_id: str
    to_warehouse_id: str
    to_location_id: str
    notes: Optional[str] = None
    lines: List[TransferLinePayload] = []


class ReceiveLinePayload(BaseModel):
    line_id: str
    received_qty: float
    damaged_qty: float = 0.0


class ReceivePayload(BaseModel):
    lines: List[ReceiveLinePayload] = []


async def _product(ctx: Context, product_id: str) -> Dict[str, Any]:
    product = await ctx.store.find_one("products", ctx.scope({"id": product_id}))
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product


@router.get("")
async def list_transfers(ctx: Context = Depends(require_permission("transfer:read")),
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                         status: Optional[TransferStatus] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    return await paginated(ctx.store, "stock_transfers", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("", status_code=201)
async def create_transfer(payload: TransferPayload,
                          ctx: Context = Depends(require_permission("transfer:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if payload.from_warehouse_id == payload.to_warehouse_id and payload.from_location_id == payload.to_location_id:
        raise ValidationError("Source and destination must differ")
    for wid in (payload.from_warehouse_id, payload.to_warehouse_id):
        if not await ctx.store.find_one("warehouses", ctx.scope({"id": wid})):
            raise NotFoundError(f"Warehouse {wid} not found")
    await _validate_location(ctx, payload.from_warehouse_id, payload.from_location_id)
    await _validate_location(ctx, payload.to_warehouse_id, payload.to_location_id)
    if not payload.lines:
        raise ValidationError("A transfer needs at least one line")

    lines = []
    for line in payload.lines:
        product = await _product(ctx, line.product_id)
        lines.append(StockTransferLine(
            product_id=product["id"], sku=product.get("sku"), product_name=product.get("name"),
            requested_qty=line.requested_qty, unit=line.unit or product.get("base_unit", "PCS"),
            batch_number=line.batch_number, notes=line.notes,
        ))

    settings = (await ctx.store.find_one("tenants", {"id": tenant_id}) or {}).get("settings") or {}
    requires_approval = bool(settings.get("require_transfer_approval"))
    transfer = StockTransfer(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "transfer"),
        from_warehouse_id=payload.from_warehouse_id, from_location_id=payload.from_location_id,
        to_warehouse_id=payload.to_warehouse_id, to_location_id=payload.to_location_id,
        status=TransferStatus.REQUESTED,
        approval_status=ApprovalStatus.PENDING.value if requires_approval else ApprovalStatus.NOT_REQUIRED.value,
        notes=payload.notes, created_by=ctx.user_id, lines=lines,
    )
    doc = transfer.model_dump(mode="python")
    await ctx.store.insert_one("stock_transfers", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="stock_transfer", entity_id=doc["id"], after=doc,
                       **ctx.client_meta())
    return doc


async def _validate_location(ctx: Context, warehouse_id: str, location_id: str) -> Dict[str, Any]:
    location = await ctx.store.find_one(
        "warehouse_locations", ctx.scope({"id": location_id, "warehouse_id": warehouse_id}))
    if not location:
        raise NotFoundError("Location not found in the selected warehouse")
    return location


@router.get("/{transfer_id}")
async def get_transfer(transfer_id: str,
                       ctx: Context = Depends(require_permission("transfer:read"))) -> Dict[str, Any]:
    transfer = await ctx.store.find_one("stock_transfers", ctx.scope({"id": transfer_id}))
    if not transfer:
        raise NotFoundError("Transfer not found")
    return transfer


@router.post("/{transfer_id}/approve")
async def approve_transfer(transfer_id: str,
                           ctx: Context = Depends(require_permission("transfer:approve"))) -> Dict[str, Any]:
    transfer = await ctx.store.find_one("stock_transfers", ctx.scope({"id": transfer_id}))
    if not transfer:
        raise NotFoundError("Transfer not found")
    await ctx.store.update_one("stock_transfers", ctx.scope({"id": transfer_id}),
                               set_fields={"status": TransferStatus.APPROVED.value,
                                           "approval_status": ApprovalStatus.APPROVED.value,
                                           "approved_by": ctx.user_id, "approved_at": utcnow(),
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("stock_transfers", {"id": transfer_id})


@router.post("/{transfer_id}/dispatch")
async def dispatch_transfer(transfer_id: str,
                            idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                            ctx: Context = Depends(require_permission("transfer:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    transfer = await ctx.store.find_one("stock_transfers", ctx.scope({"id": transfer_id}))
    if not transfer:
        raise NotFoundError("Transfer not found")
    if transfer.get("status") in (TransferStatus.IN_TRANSIT.value, TransferStatus.COMPLETED.value):
        return transfer
    if transfer.get("approval_status") == ApprovalStatus.PENDING.value:
        raise ValidationError("This transfer has not been approved yet")

    async def _dispatch() -> Dict[str, Any]:
        updated_lines = []
        for line in transfer.get("lines", []):
            product = await _product(ctx, line["product_id"])
            qty = float(line["requested_qty"])
            await post_movement(
                ctx.store, tenant_id=tenant_id, warehouse_id=transfer["from_warehouse_id"],
                location_id=transfer["from_location_id"], product=product,
                movement_type=StockMovementType.TRANSFER_OUT, quantity=-qty,
                reference_type="stock_transfer", reference_id=transfer["id"],
                reference_number=transfer["number"], batch_number=line.get("batch_number"),
                created_by=ctx.user_id,
            )
            await post_movement(
                ctx.store, tenant_id=tenant_id, warehouse_id=transfer["to_warehouse_id"],
                location_id=transfer["to_location_id"], product=product,
                movement_type=StockMovementType.TRANSFER_IN, quantity=0, in_transit_delta=qty,
                reference_type="stock_transfer", reference_id=transfer["id"],
                reference_number=transfer["number"], batch_number=line.get("batch_number"),
                created_by=ctx.user_id,
            )
            updated_lines.append({**line, "dispatched_qty": qty})
        await ctx.store.update_one(
            "stock_transfers", ctx.scope({"id": transfer_id}),
            set_fields={"lines": updated_lines, "status": TransferStatus.IN_TRANSIT.value,
                        "dispatched_at": utcnow(), "updated_at": utcnow()},
        )
        result = await ctx.store.find_one("stock_transfers", {"id": transfer_id})
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="dispatch",
                           entity_type="stock_transfer", entity_id=transfer_id,
                           description="Transfer dispatched", **ctx.client_meta())
        return result

    return await run_idempotent(
        ctx.store, tenant_id=tenant_id, key=idempotency_key,
        endpoint=f"transfers:{transfer_id}:dispatch",
        payload={"transfer_id": transfer_id}, handler=_dispatch,
    )


@router.post("/{transfer_id}/receive")
async def receive_transfer(transfer_id: str, payload: ReceivePayload,
                           ctx: Context = Depends(require_permission("transfer:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    transfer = await ctx.store.find_one("stock_transfers", ctx.scope({"id": transfer_id}))
    if not transfer:
        raise NotFoundError("Transfer not found")
    if transfer.get("status") != TransferStatus.IN_TRANSIT.value:
        raise ValidationError("Only in-transit transfers can be received")

    received_map = {line.line_id: line for line in payload.lines}
    updated_lines = []
    fully_received = True
    for line in transfer.get("lines", []):
        received = float(line.get("received_qty") or 0.0)
        if line["id"] in received_map:
            received += float(received_map[line["id"]].received_qty)
        damaged = float(line.get("damaged_qty") or 0.0)
        if line["id"] in received_map:
            damaged += float(received_map[line["id"]].damaged_qty)
        product = await _product(ctx, line["product_id"])
        if line["id"] in received_map:
            good = float(received_map[line["id"]].received_qty)
            dmg = float(received_map[line["id"]].damaged_qty)
            if good > 0:
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=transfer["to_warehouse_id"],
                    location_id=transfer["to_location_id"], product=product,
                    movement_type=StockMovementType.TRANSFER_IN, quantity=good, in_transit_delta=-good,
                    reference_type="stock_transfer", reference_id=transfer["id"],
                    reference_number=transfer["number"], batch_number=line.get("batch_number"),
                    created_by=ctx.user_id,
                )
            if dmg > 0:
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=transfer["to_warehouse_id"],
                    location_id=transfer["to_location_id"], product=product,
                    movement_type=StockMovementType.DAMAGED, quantity=dmg, damaged_delta=dmg,
                    in_transit_delta=-dmg,
                    reference_type="stock_transfer", reference_id=transfer["id"],
                    reference_number=transfer["number"], batch_number=line.get("batch_number"),
                    created_by=ctx.user_id,
                )
        if received < float(line.get("dispatched_qty") or line["requested_qty"]) - 1e-6:
            fully_received = False
        updated_lines.append({**line, "received_qty": received, "damaged_qty": damaged})

    await ctx.store.update_one(
        "stock_transfers", ctx.scope({"id": transfer_id}),
        set_fields={"lines": updated_lines,
                    "status": (TransferStatus.COMPLETED if fully_received
                               else TransferStatus.PARTIALLY_RECEIVED).value,
                    "received_at": utcnow(), "updated_at": utcnow()},
    )
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="receive",
                       entity_type="stock_transfer", entity_id=transfer_id, **ctx.client_meta())
    return await ctx.store.find_one("stock_transfers", {"id": transfer_id})


@router.post("/{transfer_id}/cancel")
async def cancel_transfer(transfer_id: str,
                          ctx: Context = Depends(require_permission("transfer:write"))) -> Dict[str, Any]:
    transfer = await ctx.store.find_one("stock_transfers", ctx.scope({"id": transfer_id}))
    if not transfer:
        raise NotFoundError("Transfer not found")
    if transfer.get("status") in (TransferStatus.IN_TRANSIT.value, TransferStatus.COMPLETED.value):
        raise ValidationError("An in-transit or completed transfer cannot be cancelled")
    await ctx.store.update_one("stock_transfers", ctx.scope({"id": transfer_id}),
                               set_fields={"status": TransferStatus.CANCELLED.value, "updated_at": utcnow()})
    return await ctx.store.find_one("stock_transfers", {"id": transfer_id})
