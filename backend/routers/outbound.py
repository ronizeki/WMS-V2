"""Outbound: sales orders, allocation, picking, packing and shipping."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import NotFoundError, ValidationError
from models import (
    PackingRecord,
    PickingTask,
    SalesOrder,
    SalesOrderLine,
    SalesOrderStatus,
    Shipment,
    ShipmentStatus,
    StockMovementType,
    TaskStatus,
    utcnow,
)
from routers.common import paginated
from services.audit import record_audit
from services.idempotency import run_idempotent
from services.inventory import allocate_stock, mark_allocations_consumed, post_movement
from services.numbering import next_number

router = APIRouter(tags=["outbound"])


class SOLinePayload(BaseModel):
    product_id: str
    ordered_qty: float
    unit_price: float = 0.0
    unit: str = "PCS"
    notes: Optional[str] = None


class SOPayload(BaseModel):
    customer_id: str
    warehouse_id: str
    requested_ship_date: Optional[datetime] = None
    priority: str = "medium"
    reference: Optional[str] = None
    notes: Optional[str] = None
    lines: List[SOLinePayload] = []


class PickingCompleteLine(BaseModel):
    line_id: str
    picked_qty: float
    discrepancy_qty: float = 0.0
    notes: Optional[str] = None


class PickingCompletePayload(BaseModel):
    lines: List[PickingCompleteLine] = []


class PackingCompletePayload(BaseModel):
    package_count: int = 1
    total_weight_kg: Optional[float] = None


class ShipmentPayload(BaseModel):
    sales_order_id: str
    carrier_name: Optional[str] = None
    tracking_reference: Optional[str] = None
    notes: Optional[str] = None


async def _product(ctx: Context, product_id: str) -> Dict[str, Any]:
    product = await ctx.store.find_one("products", ctx.scope({"id": product_id}))
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product


async def _refresh_so_status(ctx: Context, sales_order_id: str) -> Dict[str, Any]:
    order = await ctx.store.find_one("sales_orders", {"id": sales_order_id})
    lines = order.get("lines", [])
    if not lines:
        return order
    shipped_all = all(float(l.get("shipped_qty") or 0) >= float(l.get("ordered_qty") or 0) - 1e-6 for l in lines)
    shipped_any = any(float(l.get("shipped_qty") or 0) > 0 for l in lines)
    picked_all = all(float(l.get("picked_qty") or 0) >= float(l.get("ordered_qty") or 0) - 1e-6 for l in lines)
    packed_all = all(float(l.get("packed_qty") or 0) >= float(l.get("ordered_qty") or 0) - 1e-6 for l in lines)

    if shipped_all:
        status = SalesOrderStatus.SHIPPED
    elif shipped_any:
        status = SalesOrderStatus.PARTIALLY_SHIPPED
    elif packed_all:
        status = SalesOrderStatus.PACKED
    elif picked_all:
        status = SalesOrderStatus.PICKED
    else:
        status = order.get("status", SalesOrderStatus.CONFIRMED.value)
    await ctx.store.update_one("sales_orders", {"id": sales_order_id},
                               set_fields={"status": status.value if hasattr(status, "value") else status,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("sales_orders", {"id": sales_order_id})


# ---------------------------------------------------------------- sales orders

@router.get("/sales-orders")
async def list_sales_orders(ctx: Context = Depends(require_permission("outbound:read")),
                            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                            status: Optional[SalesOrderStatus] = None,
                            warehouse_id: Optional[str] = None,
                            customer_id: Optional[str] = None,
                            search: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if customer_id:
        query["customer_id"] = customer_id
    if search:
        query["$or"] = [
            {"number": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "sales_orders", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("/sales-orders", status_code=201)
async def create_sales_order(payload: SOPayload,
                             ctx: Context = Depends(require_permission("outbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    customer = await ctx.store.find_one("customers", ctx.scope({"id": payload.customer_id}))
    if not customer:
        raise NotFoundError("Customer not found")
    if not await ctx.store.find_one("warehouses", ctx.scope({"id": payload.warehouse_id})):
        raise NotFoundError("Warehouse not found")
    if not payload.lines:
        raise ValidationError("A sales order needs at least one line")

    lines = []
    total = 0.0
    for line in payload.lines:
        product = await _product(ctx, line.product_id)
        total += line.ordered_qty * line.unit_price
        lines.append(SalesOrderLine(
            product_id=product["id"], sku=product.get("sku"), product_name=product.get("name"),
            ordered_qty=line.ordered_qty, unit=line.unit or product.get("base_unit", "PCS"),
            unit_price=line.unit_price, notes=line.notes,
        ))

    order = SalesOrder(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "sales_order"),
        customer_id=customer["id"], customer_name=customer.get("name"),
        warehouse_id=payload.warehouse_id,
        requested_ship_date=payload.requested_ship_date,
        priority=payload.priority, reference=payload.reference, notes=payload.notes,
        total_amount=total, created_by=ctx.user_id, lines=lines,
        status=SalesOrderStatus.DRAFT,
    )
    doc = order.model_dump(mode="python")
    await ctx.store.insert_one("sales_orders", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="sales_order", entity_id=doc["id"], after=doc,
                       **ctx.client_meta())
    return doc


@router.get("/sales-orders/{order_id}")
async def get_sales_order(order_id: str,
                          ctx: Context = Depends(require_permission("outbound:read"))) -> Dict[str, Any]:
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": order_id}))
    if not order:
        raise NotFoundError("Sales order not found")
    order["picking_tasks"] = await ctx.store.find_many("picking_tasks",
                                                       ctx.scope({"sales_order_id": order_id}))
    order["shipments"] = await ctx.store.find_many("shipments",
                                                   ctx.scope({"sales_order_id": order_id}))
    return order


@router.post("/sales-orders/{order_id}/confirm")
async def confirm_sales_order(order_id: str,
                              ctx: Context = Depends(require_permission("outbound:write"))) -> Dict[str, Any]:
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": order_id}))
    if not order:
        raise NotFoundError("Sales order not found")
    if order.get("status") == SalesOrderStatus.CANCELLED.value:
        raise ValidationError("A cancelled order cannot be confirmed")
    await ctx.store.update_one("sales_orders", ctx.scope({"id": order_id}),
                               set_fields={"status": SalesOrderStatus.CONFIRMED.value,
                                           "updated_at": utcnow()})
    return await ctx.store.find_one("sales_orders", {"id": order_id})


@router.post("/sales-orders/{order_id}/cancel")
async def cancel_sales_order(order_id: str,
                             ctx: Context = Depends(require_permission("outbound:write"))) -> Dict[str, Any]:
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": order_id}))
    if not order:
        raise NotFoundError("Sales order not found")
    if any(float(l.get("shipped_qty") or 0) > 0 for l in order.get("lines", [])):
        raise ValidationError("An order with shipped quantities cannot be cancelled")

    # release any active reservations
    from services.inventory import release_allocations
    for line in order.get("lines", []):
        allocations = line.get("allocations") or []
        if allocations:
            await release_allocations(ctx.store, allocations, tenant_id=ctx.require_tenant())
    # cancel open picking tasks
    for task in await ctx.store.find_many("picking_tasks", ctx.scope({"sales_order_id": order_id,
                                                                     "status": {"$in": ["pending", "in_progress"]}})):
        await ctx.store.update_one("picking_tasks", {"id": task["id"]},
                                   set_fields={"status": TaskStatus.CANCELLED.value, "updated_at": utcnow()})
    await ctx.store.update_one("sales_orders", ctx.scope({"id": order_id}),
                               set_fields={"status": SalesOrderStatus.CANCELLED.value, "updated_at": utcnow()})
    return await ctx.store.find_one("sales_orders", {"id": order_id})


@router.post("/sales-orders/{order_id}/allocate")
async def allocate_sales_order(order_id: str,
                               idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                               ctx: Context = Depends(require_permission("outbound:pick"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": order_id}))
    if not order:
        raise NotFoundError("Sales order not found")
    if order.get("status") in (SalesOrderStatus.CANCELLED.value, SalesOrderStatus.SHIPPED.value):
        raise ValidationError("This order can no longer be allocated")

    async def _allocate() -> Dict[str, Any]:
        updated_lines = []
        for line in order.get("lines", []):
            product = await _product(ctx, line["product_id"])
            outstanding = float(line.get("ordered_qty") or 0) - float(line.get("reserved_qty") or 0)
            if outstanding <= 0:
                updated_lines.append(line)
                continue
            allocations = await allocate_stock(
                ctx.store, tenant_id=tenant_id, warehouse_id=order["warehouse_id"],
                product=product, quantity=outstanding,
                sales_order_id=order["id"], sales_order_line_id=line["id"],
                created_by=ctx.user_id,
            )
            existing = line.get("allocations") or []
            reserved = float(line.get("reserved_qty") or 0) + sum(float(a["quantity"]) for a in allocations)
            updated_lines.append({**line, "allocations": existing + allocations,
                                  "reserved_qty": reserved})

        # create a picking task covering the reserved quantities
        task_lines = []
        for line in updated_lines:
            for allocation in line.get("allocations") or []:
                task_lines.append({
                    "sales_order_line_id": line["id"],
                    "product_id": line["product_id"],
                    "sku": line.get("sku"), "product_name": line.get("product_name"),
                    "location_id": allocation["location_id"],
                    "quantity": allocation["quantity"],
                })
        task = None
        if task_lines:
            picking = PickingTask(
                tenant_id=tenant_id,
                number=await next_number(ctx.store, tenant_id, "picking"),
                sales_order_id=order["id"], sales_order_number=order["number"],
                warehouse_id=order["warehouse_id"],
                priority=order.get("priority", "medium"),
                status=TaskStatus.PENDING,
            )
            from models import PickingTaskLine
            picking.lines = [PickingTaskLine(**tl) for tl in task_lines]
            task = picking.model_dump(mode="python")
            await ctx.store.insert_one("picking_tasks", task)

        await ctx.store.update_one(
            "sales_orders", ctx.scope({"id": order_id}),
            set_fields={"lines": updated_lines, "status": SalesOrderStatus.ALLOCATED.value,
                        "updated_at": utcnow()},
        )
        result = await ctx.store.find_one("sales_orders", {"id": order_id})
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="allocate",
                           entity_type="sales_order", entity_id=order_id,
                           description="Reserved stock for order", **ctx.client_meta())
        return {"sales_order": result, "picking_task": task}

    return await run_idempotent(
        ctx.store, tenant_id=tenant_id, key=idempotency_key,
        endpoint=f"sales_orders:{order_id}:allocate",
        payload={"order_id": order_id}, handler=_allocate,
    )


# ---------------------------------------------------------------- picking

@router.get("/picking")
async def list_picking(ctx: Context = Depends(require_permission("outbound:read")),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       status: Optional[TaskStatus] = None,
                       warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "picking_tasks", query, page=page, page_size=page_size)


@router.post("/picking/{task_id}/start")
async def start_picking(task_id: str,
                        ctx: Context = Depends(require_permission("outbound:pick"))) -> Dict[str, Any]:
    task = await ctx.store.find_one("picking_tasks", ctx.scope({"id": task_id}))
    if not task:
        raise NotFoundError("Picking task not found")
    await ctx.store.update_one("picking_tasks", ctx.scope({"id": task_id}),
                               set_fields={"status": TaskStatus.IN_PROGRESS.value,
                                           "assigned_to": ctx.user_id, "started_at": utcnow(),
                                           "updated_at": utcnow()})
    await ctx.store.update_one("sales_orders", ctx.scope({"id": task["sales_order_id"]}),
                               set_fields={"status": SalesOrderStatus.PICKING.value, "updated_at": utcnow()})
    return await ctx.store.find_one("picking_tasks", {"id": task_id})


@router.post("/picking/{task_id}/complete")
async def complete_picking(task_id: str, payload: PickingCompletePayload,
                           ctx: Context = Depends(require_permission("outbound:pick"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    task = await ctx.store.find_one("picking_tasks", ctx.scope({"id": task_id}))
    if not task:
        raise NotFoundError("Picking task not found")
    if task.get("status") == TaskStatus.COMPLETED.value:
        return task

    submitted = {line.line_id: line for line in payload.lines}
    updated_task_lines = []
    picked_by_so_line: Dict[str, float] = {}
    for line in task.get("lines", []):
        entry = submitted.get(line["id"])
        picked = float(entry.picked_qty) if entry else float(line["quantity"])
        discrepancy = float(entry.discrepancy_qty) if entry else 0.0
        updated_task_lines.append({**line, "picked_qty": picked, "discrepancy_qty": discrepancy,
                                   "scanned": True, "notes": entry.notes if entry else line.get("notes")})
        picked_by_so_line[line["sales_order_line_id"]] = picked_by_so_line.get(line["sales_order_line_id"], 0.0) + picked

    await ctx.store.update_one("picking_tasks", ctx.scope({"id": task_id}),
                               set_fields={"lines": updated_task_lines,
                                           "status": TaskStatus.COMPLETED.value,
                                           "completed_at": utcnow(), "completed_by": ctx.user_id,
                                           "updated_at": utcnow()})

    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": task["sales_order_id"]}))
    order_lines = []
    for line in order.get("lines", []):
        if line["id"] in picked_by_so_line:
            order_lines.append({**line, "picked_qty": picked_by_so_line[line["id"]]})
        else:
            order_lines.append(line)
    await ctx.store.update_one("sales_orders", ctx.scope({"id": order["id"]}),
                               set_fields={"lines": order_lines, "updated_at": utcnow()})
    await _refresh_so_status(ctx, order["id"])
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="pick",
                       entity_type="picking_task", entity_id=task_id, description="Picking completed",
                       **ctx.client_meta())
    return await ctx.store.find_one("picking_tasks", {"id": task_id})


# ---------------------------------------------------------------- packing

@router.get("/packing")
async def list_packing(ctx: Context = Depends(require_permission("outbound:read")),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                       status: Optional[TaskStatus] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    return await paginated(ctx.store, "packing_records", query, page=page, page_size=page_size)


@router.post("/sales-orders/{order_id}/packing", status_code=201)
async def create_packing(order_id: str,
                         ctx: Context = Depends(require_permission("outbound:pack"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": order_id}))
    if not order:
        raise NotFoundError("Sales order not found")
    if not any(float(l.get("picked_qty") or 0) > 0 for l in order.get("lines", [])):
        raise ValidationError("Pick the order before packing")

    from models import PackingRecordLine
    record = PackingRecord(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "packing"),
        sales_order_id=order["id"], sales_order_number=order["number"],
        warehouse_id=order["warehouse_id"], status=TaskStatus.PENDING,
        lines=[PackingRecordLine(product_id=l["product_id"], sku=l.get("sku"),
                                 quantity=float(l.get("picked_qty") or 0))
               for l in order.get("lines", []) if float(l.get("picked_qty") or 0) > 0],
    )
    doc = record.model_dump(mode="python")
    await ctx.store.insert_one("packing_records", doc)
    return doc


@router.post("/packing/{packing_id}/complete")
async def complete_packing(packing_id: str, payload: PackingCompletePayload,
                           ctx: Context = Depends(require_permission("outbound:pack"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    record = await ctx.store.find_one("packing_records", ctx.scope({"id": packing_id}))
    if not record:
        raise NotFoundError("Packing record not found")
    if record.get("status") == TaskStatus.COMPLETED.value:
        return record
    updated_lines = [{**line, "packed_qty": float(line.get("quantity") or 0)} for line in record.get("lines", [])]
    await ctx.store.update_one("packing_records", ctx.scope({"id": packing_id}),
                               set_fields={"lines": updated_lines, "status": TaskStatus.COMPLETED.value,
                                           "package_count": payload.package_count,
                                           "total_weight_kg": payload.total_weight_kg,
                                           "completed_at": utcnow(), "completed_by": ctx.user_id,
                                           "updated_at": utcnow()})
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": record["sales_order_id"]}))
    packed_map = {l["product_id"]: float(l.get("packed_qty") or 0) for l in updated_lines}
    order_lines = [{**line, "packed_qty": packed_map.get(line["product_id"], float(line.get("packed_qty") or 0))}
                   for line in order.get("lines", [])]
    await ctx.store.update_one("sales_orders", ctx.scope({"id": order["id"]}),
                               set_fields={"lines": order_lines, "updated_at": utcnow()})
    await _refresh_so_status(ctx, order["id"])
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="pack",
                       entity_type="packing_record", entity_id=packing_id, **ctx.client_meta())
    return await ctx.store.find_one("packing_records", {"id": packing_id})


# ---------------------------------------------------------------- shipments

@router.get("/shipments")
async def list_shipments(ctx: Context = Depends(require_permission("outbound:read")),
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                         status: Optional[ShipmentStatus] = None,
                         warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if status:
        query["status"] = status.value
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    return await paginated(ctx.store, "shipments", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])


@router.post("/shipments", status_code=201)
async def create_shipment(payload: ShipmentPayload,
                          ctx: Context = Depends(require_permission("outbound:ship"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    order = await ctx.store.find_one("sales_orders", ctx.scope({"id": payload.sales_order_id}))
    if not order:
        raise NotFoundError("Sales order not found")

    from models import ShipmentLine
    lines = []
    for line in order.get("lines", []):
        outstanding = float(line.get("ordered_qty") or 0) - float(line.get("shipped_qty") or 0)
        if outstanding <= 0:
            continue
        lines.append(ShipmentLine(sales_order_line_id=line["id"], product_id=line["product_id"],
                                  sku=line.get("sku"), product_name=line.get("product_name"),
                                  quantity=outstanding, unit=line.get("unit", "PCS")))
    if not lines:
        raise ValidationError("There is nothing left to ship for this order")

    shipment = Shipment(
        tenant_id=tenant_id,
        number=await next_number(ctx.store, tenant_id, "shipment"),
        sales_order_id=order["id"], sales_order_number=order["number"],
        customer_id=order.get("customer_id"), customer_name=order.get("customer_name"),
        warehouse_id=order["warehouse_id"],
        carrier_name=payload.carrier_name, tracking_reference=payload.tracking_reference,
        notes=payload.notes, created_by=ctx.user_id, lines=lines,
        status=ShipmentStatus.DRAFT,
    )
    doc = shipment.model_dump(mode="python")
    await ctx.store.insert_one("shipments", doc)
    return doc


@router.post("/shipments/{shipment_id}/post")
async def post_shipment(shipment_id: str,
                        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
                        ctx: Context = Depends(require_permission("outbound:ship"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    shipment = await ctx.store.find_one("shipments", ctx.scope({"id": shipment_id}))
    if not shipment:
        raise NotFoundError("Shipment not found")
    if shipment.get("posted"):
        return shipment

    async def _post() -> Dict[str, Any]:
        order = await ctx.store.find_one("sales_orders", ctx.scope({"id": shipment["sales_order_id"]}))
        order_line_map = {l["id"]: l for l in order.get("lines", [])}
        settings = (await ctx.store.find_one("tenants", {"id": tenant_id}) or {}).get("settings") or {}
        allow_negative = bool(settings.get("allow_negative_stock"))

        shipped_by_line: Dict[str, float] = {}
        for ship_line in shipment.get("lines", []):
            so_line = order_line_map.get(ship_line.get("sales_order_line_id"))
            remaining = float(ship_line["quantity"])
            allocations = (so_line or {}).get("allocations") or []
            # consume allocations first (reserved stock), then any remainder from the warehouse
            for allocation in allocations:
                if remaining <= 1e-6:
                    break
                take = min(float(allocation["quantity"]), remaining)
                product = await _product(ctx, ship_line["product_id"])
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=shipment["warehouse_id"],
                    location_id=allocation["location_id"], product=product,
                    movement_type=StockMovementType.OUTBOUND_SHIPMENT, quantity=-take,
                    reserved_delta=-take,
                    reference_type="shipment", reference_id=shipment["id"],
                    reference_number=shipment["number"], batch_number=allocation.get("batch_number"),
                    created_by=ctx.user_id, allow_negative=allow_negative,
                )
                remaining -= take
            if remaining > 1e-6:
                product = await _product(ctx, ship_line["product_id"])
                location = await ctx.store.find_one(
                    "warehouse_locations",
                    ctx.scope({"warehouse_id": shipment["warehouse_id"], "is_pickable": True}))
                location_id = location["id"] if location else None
                if not location_id:
                    raise ValidationError("No pickable location available to ship from")
                await post_movement(
                    ctx.store, tenant_id=tenant_id, warehouse_id=shipment["warehouse_id"],
                    location_id=location_id, product=product,
                    movement_type=StockMovementType.OUTBOUND_SHIPMENT, quantity=-remaining,
                    reference_type="shipment", reference_id=shipment["id"],
                    reference_number=shipment["number"], created_by=ctx.user_id,
                    allow_negative=allow_negative,
                )
            shipped_by_line[ship_line.get("sales_order_line_id")] = float(ship_line["quantity"])

        if order:
            new_lines = []
            for line in order.get("lines", []):
                add = shipped_by_line.get(line["id"], 0.0)
                new_lines.append({**line, "shipped_qty": float(line.get("shipped_qty") or 0) + add})
            await ctx.store.update_one("sales_orders", ctx.scope({"id": order["id"]}),
                                       set_fields={"lines": new_lines, "updated_at": utcnow()})

        await ctx.store.update_one(
            "shipments", ctx.scope({"id": shipment_id}),
            set_fields={"status": ShipmentStatus.IN_TRANSIT.value, "posted": True,
                        "posted_at": utcnow(), "posted_by": ctx.user_id,
                        "shipped_date": utcnow(), "updated_at": utcnow()},
        )
        await mark_allocations_consumed(ctx.store, [
            a for line in (order or {}).get("lines", []) for a in (line.get("allocations") or [])
        ])
        if order:
            await _refresh_so_status(ctx, order["id"])
        result = await ctx.store.find_one("shipments", {"id": shipment_id})
        await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="ship",
                           entity_type="shipment", entity_id=shipment_id,
                           description="Shipment posted, stock dispatched", **ctx.client_meta())
        return result

    return await run_idempotent(
        ctx.store, tenant_id=tenant_id, key=idempotency_key,
        endpoint=f"shipments:{shipment_id}:post",
        payload={"shipment_id": shipment_id}, handler=_post,
    )


@router.post("/shipments/{shipment_id}/deliver")
async def deliver_shipment(shipment_id: str,
                           ctx: Context = Depends(require_permission("outbound:ship"))) -> Dict[str, Any]:
    shipment = await ctx.store.find_one("shipments", ctx.scope({"id": shipment_id}))
    if not shipment:
        raise NotFoundError("Shipment not found")
    await ctx.store.update_one("shipments", ctx.scope({"id": shipment_id}),
                               set_fields={"status": ShipmentStatus.DELIVERED.value,
                                           "delivered_date": utcnow(), "updated_at": utcnow()})
    return await ctx.store.find_one("shipments", {"id": shipment_id})
