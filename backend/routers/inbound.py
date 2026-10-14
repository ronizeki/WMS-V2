"""Inbound: purchase orders, goods receipts and putaway."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError, ValidationError
from models import (
    GoodsReceipt,
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    PutawayStatus,
    PutawayTask,
    StockMovementType,
    utcnow,
)
from routers.common import paginated
from services.audit import record_audit
from services.idempotency import run_idempotent
from services.inventory import post_movement
from services.numbering import next_number

router = APIRouter(tags=["inbound"])


class POLinePayload(BaseModel):
    product_id: str
    ordered_qty: float
    unit_cost: float = 0.0
    unit: str = "PCS"
    notes: Optional[str] = None


class POPayload(BaseModel):
    supplier_id: str
    warehouse_id: str
    expected_date: Optional[datetime] = None
    currency: str = "IDR"
    notes: Optional[str] = None
    lines: List[POLinePayload] = []


class ReceiptLinePayload(BaseModel):
    po_line_id: Optional[str] = None
    product_id: str
    expected_qty: float = 0.0
    received_qty: float = 0.0
    damaged_qty: float = 0.0
    rejected_qty: float = 0.0
    unit: str = "PCS"
    unit_cost: float = 0.0
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    receiving_location_id: Optional[str] = None
    notes: Optional[str] = None


class ReceiptPayload(BaseModel):
    warehouse_id: str
    purchase_order_id: Optional[str] = None
    supplier_id: Optional[str] = None
    notes: Optional[str] = None
    lines: List[ReceiptLinePayload] = []


class PutawayCompletePayload(BaseModel):
    to_location_id: str
    quantity: Optional[float] = None


async def _product(ctx: Context, product_id: str) -> Dict[str, Any]:
    product = await ctx.store.find_one("products", ctx.scope({"id": product_id}))
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product


async def _default_receiving_location(ctx: Context, warehouse_id: str) -> Dict[str, Any]:
    location = await ctx.store.find_one(
        "warehouse_locations",
        ctx.scope({"warehouse_id": warehouse_id, "location_type": "receiving"}),
    )
    if location:
        return location
    location = await ctx.store.find_one("warehouse_locations", ctx.scope({"warehouse_id": warehouse_id}))
    if not location:
        raise ValidationError("The warehouse has no locations defined. Create a location first.")
    return location


# ---------------------------------------------------------------- purchase orders

@router.get("/purchase-orders")
async def list_purchase_orders(ctx: Context = Depends(require_permission("inbound:read")),
                               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                               status: Optional[PurchaseOrderStatus] = None,
                               warehouse_id: Optional[str] = None,
                               supplier_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if supplier_id:
        query["supplier_id"] = supplier_id
    return await paginated(ctx.store, "purchase_orders", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("/purchase-orders", status_code=201)
async def create_purchase_order(payload: POPayload,
                                ctx: Context = Depends(require_permission("inbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    supplier = await ctx.store.find_one("suppliers", ctx.scope({"id": payload.supplier_id}))
    if not supplier:
        raise NotFoundError("Supplier not found")
    if not await ctx.store.find_one("warehouses", ctx.scope({"id": payload.warehouse_id})):
        raise NotFoundError("Warehouse not found")
    if not payload.lines:
        raise ValidationError("A purchase order needs at least one line")

    lines = []
    total = 0.0
    for line in payload.lines:
        product = await _product(ctx, line.product_id)
        total += line.ordered_qty * line.unit_cost
        lines.append({
            "product_id": product["id"],
            "sku": product.get("sku"),
            "product_name": product.get("name"),
            "ordered_qty": line.ordered_qty,
            "received_qty": 0.0,
            "unit": line.unit or product.get("base_unit", "PCS"),
            "unit_cost": line.unit_cost,
            "notes": line.notes,
        })

    from models import PurchaseOrderLine
    po = PurchaseOrder(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "purchase_order"),
        supplier_id=supplier["id"],
        supplier_name=supplier.get("name"),
        warehouse_id=payload.warehouse_id,
        expected_date=payload.expected_date,
        currency=payload.currency,
        notes=payload.notes,
        total_amount=total,
        created_by=ctx.user_id,
        lines=[PurchaseOrderLine(**line) for line in lines],
        status=PurchaseOrderStatus.PENDING,
    )
    doc = po.model_dump(mode="python")
    await ctx.store.insert_one("purchase_orders", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="purchase_order", entity_id=doc["id"], after=doc,
                       **ctx.client_meta())
    return doc


@router.get("/purchase-orders/{po_id}")
async def get_purchase_order(po_id: str,
                             ctx: Context = Depends(require_permission("inbound:read"))) -> Dict[str, Any]:
    po = await ctx.store.find_one("purchase_orders", ctx.scope({"id": po_id}))
    if not po:
        raise NotFoundError("Purchase order not found")
    return po


@router.post("/purchase-orders/{po_id}/approve")
async def approve_purchase_order(po_id: str,
                                 ctx: Context = Depends(require_permission("inbound:approve"))) -> Dict[str, Any]:
    po = await ctx.store.find_one("purchase_orders", ctx.scope({"id": po_id}))
    if not po:
        raise NotFoundError("Purchase order not found")
    await ctx.store.update_one("purchase_orders", ctx.scope({"id": po_id}),
                               set_fields={"status": PurchaseOrderStatus.APPROVED.value,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("purchase_orders", {"id": po_id})


@router.post("/purchase-orders/{po_id}/cancel")
async def cancel_purchase_order(po_id: str,
                                ctx: Context = Depends(require_permission("inbound:approve"))) -> Dict[str, Any]:
    po = await ctx.store.find_one("purchase_orders", ctx.scope({"id": po_id}))
    if not po:
        raise NotFoundError("Purchase order not found")
    await ctx.store.update_one("purchase_orders", ctx.scope({"id": po_id}),
                               set_fields={"status": PurchaseOrderStatus.CANCELLED.value,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("purchase_orders", {"id": po_id})


# ---------------------------------------------------------------- goods receipts

@router.get("/goods-receipts")
async def list_goods_receipts(ctx: Context = Depends(require_permission("inbound:read")),
                              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                              status: Optional[GoodsReceiptStatus] = None,
                              warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "goods_receipts", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("/goods-receipts", status_code=201)
async def create_goods_receipt(payload: ReceiptPayload,
                               ctx: Context = Depends(require_permission("inbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if not await ctx.store.find_one("warehouses", ctx.scope({"id": payload.warehouse_id})):
        raise NotFoundError("Warehouse not found")

    po = None
    supplier_id = payload.supplier_id
    supplier_name = None
    if payload.purchase_order_id:
        po = await ctx.store.find_one("purchase_orders", ctx.scope({"id": payload.purchase_order_id}))
        if not po:
            raise NotFoundError("Purchase order not found")
        supplier_id = po["supplier_id"]
        supplier_name = po.get("supplier_name")

    lines: List[Dict[str, Any]] = []
    if payload.lines:
        for line in payload.lines:
            product = await _product(ctx, line.product_id)
            lines.append({
                "po_line_id": line.po_line_id,
                "product_id": product["id"],
                "sku": product.get("sku"),
                "product_name": product.get("name"),
                "expected_qty": line.expected_qty,
                "received_qty": line.received_qty,
                "damaged_qty": line.damaged_qty,
                "rejected_qty": line.rejected_qty,
                "unit": line.unit or product.get("base_unit", "PCS"),
                "unit_cost": line.unit_cost,
                "batch_number": line.batch_number,
                "expiry_date": line.expiry_date,
                "receiving_location_id": line.receiving_location_id,
                "notes": line.notes,
            })
    elif po:
        from models import GoodsReceiptLine
        for po_line in po.get("lines", []):
            outstanding = float(po_line.get("ordered_qty") or 0) - float(po_line.get("received_qty") or 0)
            if outstanding <= 0:
                continue
            lines.append({
                "po_line_id": po_line["id"],
                "product_id": po_line["product_id"],
                "sku": po_line.get("sku"),
                "product_name": po_line.get("product_name"),
                "expected_qty": outstanding,
                "received_qty": outstanding,
                "damaged_qty": 0.0,
                "rejected_qty": 0.0,
                "unit": po_line.get("unit", "PCS"),
                "unit_cost": po_line.get("unit_cost", 0.0),
                "batch_number": None,
                "expiry_date": None,
                "receiving_location_id": None,
                "notes": None,
            })
    else:
        raise ValidationError("Provide either receipt lines or a purchase order")

    if not lines:
        raise ValidationError("Nothing left to receive for this purchase order")

    receipt = GoodsReceipt(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "goods_receipt"),
        purchase_order_id=po["id"] if po else None,
        purchase_order_number=po.get("number") if po else None,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
        created_by=ctx.user_id,
        status=GoodsReceiptStatus.DRAFT,
    )
    from models import GoodsReceiptLine
    receipt.lines = [GoodsReceiptLine(**line) for line in lines]
    doc = receipt.model_dump(mode="python")
    await ctx.store.insert_one("goods_receipts", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="goods_receipt", entity_id=doc["id"], after=doc,
                       **ctx.client_meta())
    return doc


@router.get("/goods-receipts/{receipt_id}")
async def get_goods_receipt(receipt_id: str,
                            ctx: Context = Depends(require_permission("inbound:read"))) -> Dict[str, Any]:
    receipt = await ctx.store.find_one("goods_receipts", ctx.scope({"id": receipt_id}))
    if not receipt:
        raise NotFoundError("Goods receipt not found")
    return receipt


@router.post("/goods-receipts/{receipt_id}/post")
async def post_goods_receipt(receipt_id: str,
                             idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                             ctx: Context = Depends(require_permission("inbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    receipt = await ctx.store.find_one("goods_receipts", ctx.scope({"id": receipt_id}))
    if not receipt:
        raise NotFoundError("Goods receipt not found")
    if receipt.get("posted"):
        return receipt

    async def _post() -> Dict[str, Any]:
        settings = (await ctx.store.find_one("tenants", {"id": tenant_id}) or {}).get("settings") or {}
        auto_putaway = bool(settings.get("auto_create_putaway_tasks", True))
        default_location = await _default_receiving_location(ctx, receipt["warehouse_id"])

        updated_lines = []
        for line in receipt.get("lines", []):
            good_qty = float(line.get("received_qty") or 0.0) - float(line.get("damaged_qty") or 0.0)
            damaged_qty = float(line.get("damaged_qty") or 0.0)
            location_id = line.get("receiving_location_id") or default_location["id"]
            product = await _product(ctx, line["product_id"])

            if good_qty > 0:
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=receipt["warehouse_id"],
                    location_id=location_id, product=product,
                    movement_type=StockMovementType.INBOUND_RECEIPT,
                    quantity=good_qty, unit_cost=float(line.get("unit_cost") or 0.0),
                    reference_type="goods_receipt", reference_id=receipt["id"],
                    reference_number=receipt["number"],
                    batch_number=line.get("batch_number"), expiry_date=line.get("expiry_date"),
                    notes=line.get("notes"), created_by=ctx.user_id,
                )
            if damaged_qty > 0:
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=receipt["warehouse_id"],
                    location_id=location_id, product=product,
                    movement_type=StockMovementType.DAMAGED,
                    quantity=damaged_qty, unit_cost=float(line.get("unit_cost") or 0.0),
                    damaged_delta=damaged_qty,
                    reference_type="goods_receipt", reference_id=receipt["id"],
                    reference_number=receipt["number"],
                    batch_number=line.get("batch_number"), created_by=ctx.user_id,
                )

            if auto_putaway and good_qty > 0:
                task = PutawayTask(
                    tenant_id=tenant_id,
                    number=await next_number(ctx.store, tenant_id, "putaway"),
                    goods_receipt_id=receipt["id"],
                    warehouse_id=receipt["warehouse_id"],
                    product_id=product["id"],
                    sku=product.get("sku"), product_name=product.get("name"),
                    quantity=good_qty,
                    from_location_id=location_id,
                    batch_number=line.get("batch_number"),
                    expiry_date=line.get("expiry_date"),
                    status=PutawayStatus.PENDING,
                )
                await ctx.store.insert_one("putaway_tasks", task.model_dump(mode="python"))

            updated_lines.append({**line, "putaway_qty": 0.0})

        await ctx.store.update_one(
            "goods_receipts", ctx.scope({"id": receipt_id}),
            set_fields={"status": GoodsReceiptStatus.COMPLETED.value, "posted": True,
                        "posted_at": utcnow(), "posted_by": ctx.user_id,
                        "lines": updated_lines, "updated_at": utcnow()},
        )

        # Update the linked purchase order
        if receipt.get("purchase_order_id"):
            po = await ctx.store.find_one("purchase_orders", ctx.scope({"id": receipt["purchase_order_id"]}))
            if po:
                line_map = {l["id"]: l for l in po.get("lines", [])}
                for line in receipt.get("lines", []):
                    po_line = line_map.get(line.get("po_line_id"))
                    if po_line:
                        po_line["received_qty"] = float(po_line.get("received_qty") or 0.0) + float(line.get("received_qty") or 0.0)
                fully = all(float(l.get("received_qty") or 0) >= float(l.get("ordered_qty") or 0)
                            for l in po.get("lines", []))
                await ctx.store.update_one(
                    "purchase_orders", ctx.scope({"id": po["id"]}),
                    set_fields={
                        "lines": po["lines"],
                        "status": (PurchaseOrderStatus.RECEIVED if fully
                                   else PurchaseOrderStatus.PARTIALLY_RECEIVED).value,
                        "updated_at": utcnow(),
                    },
                )

        result = await ctx.store.find_one("goods_receipts", {"id": receipt_id})
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="post",
                           entity_type="goods_receipt", entity_id=receipt_id, after=result,
                           **ctx.client_meta())
        return result

    return await run_idempotent(
        ctx.store, tenant_id=tenant_id, key=idempotency_key,
        endpoint=f"goods_receipts:{receipt_id}:post",
        payload={"receipt_id": receipt_id}, handler=_post,
    )


# ---------------------------------------------------------------- putaway

@router.get("/putaway")
async def list_putaway(ctx: Context = Depends(require_permission("inbound:read")),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       status: Optional[PutawayStatus] = None,
                       warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "putaway_tasks", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("/putaway/{task_id}/complete")
async def complete_putaway(task_id: str, payload: PutawayCompletePayload,
                           ctx: Context = Depends(require_permission("inbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    task = await ctx.store.find_one("putaway_tasks", ctx.scope({"id": task_id}))
    if not task:
        raise NotFoundError("Putaway task not found")
    if task.get("status") == PutawayStatus.COMPLETED.value:
        return task
    target = await ctx.store.find_one(
        "warehouse_locations", ctx.scope({"id": payload.to_location_id,
                                          "warehouse_id": task["warehouse_id"]}))
    if not target:
        raise NotFoundError("Target location not found in this warehouse")

    qty = float(payload.quantity if payload.quantity is not None else task["quantity"])
    already = float(task.get("putaway_qty") or 0.0)
    move_qty = min(qty, float(task["quantity"]) - already)
    if move_qty <= 0:
        raise ValidationError("Nothing left to put away for this task")

    product = await _product(ctx, task["product_id"])
    from_location = task.get("from_location_id")
    if from_location:
        await post_movement(
            ctx.store, tenant_id=tenant_id, warehouse_id=task["warehouse_id"],
            location_id=from_location, product=product,
            movement_type=StockMovementType.PUTAWAY, quantity=-move_qty,
            reference_type="putaway", reference_id=task["id"], reference_number=task["number"],
            batch_number=task.get("batch_number"),
            reason="putaway out", created_by=ctx.user_id,
        )
    await post_movement(
        ctx.store, tenant_id=tenant_id, warehouse_id=task["warehouse_id"],
        location_id=target["id"], product=product,
        movement_type=StockMovementType.PUTAWAY, quantity=move_qty,
        reference_type="putaway", reference_id=task["id"], reference_number=task["number"],
        batch_number=task.get("batch_number"), expiry_date=task.get("expiry_date"),
        reason="putaway in", created_by=ctx.user_id,
    )

    new_putaway = already + move_qty
    status = (PutawayStatus.COMPLETED.value if new_putaway >= float(task["quantity"]) - 1e-6
              else PutawayStatus.IN_PROGRESS.value)
    await ctx.store.update_one(
        "putaway_tasks", ctx.scope({"id": task_id}),
        set_fields={
            "to_location_id": target["id"],
            "putaway_qty": new_putaway,
            "status": status,
            "completed_at": utcnow() if status == PutawayStatus.COMPLETED.value else None,
            "completed_by": ctx.user_id if status == PutawayStatus.COMPLETED.value else None,
            "updated_at": utcnow(),
        },
    )
    return await ctx.store.find_one("putaway_tasks", {"id": task_id})
