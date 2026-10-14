"""Dashboard KPIs and operational reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from deps import Context, require_permission

router = APIRouter(tags=["reports"])


def _sum(rows: List[Dict[str, Any]], field: str) -> float:
    return round(sum(float(r.get(field) or 0.0) for r in rows), 4)


@router.get("/dashboard")
async def dashboard(ctx: Context = Depends(require_permission("dashboard:read"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    store = ctx.store

    products = await store.find_many("products", ctx.scope({"is_archived": False}))
    balances = await store.find_many("inventory_balances", ctx.scope())
    warehouses = await store.find_many("warehouses", ctx.scope())

    total_value = _sum(balances, "total_value")
    total_on_hand = _sum(balances, "quantity_on_hand")
    total_available = _sum(balances, "quantity_available")

    stock_by_product: Dict[str, float] = {}
    for balance in balances:
        stock_by_product[balance["product_id"]] = stock_by_product.get(balance["product_id"], 0.0) + float(
            balance.get("quantity_available") or 0.0)
    low_stock = [p for p in products
                 if stock_by_product.get(p["id"], 0.0) < float(p.get("reorder_point") or 0.0)]

    open_orders = await store.find_many(
        "sales_orders",
        ctx.scope({"status": {"$in": ["confirmed", "allocated", "picking", "picked", "packing", "packed"]}}))
    pending_receipts = await store.count("goods_receipts", ctx.scope({"posted": False}))
    pending_putaway = await store.count("putaway_tasks", ctx.scope({"status": {"$in": ["pending", "in_progress"]}}))
    open_picking = await store.count("picking_tasks", ctx.scope({"status": {"$in": ["pending", "in_progress"]}}))
    in_transit = await store.count("shipments", ctx.scope({"status": "in_transit"}))
    open_transfers = await store.count("stock_transfers", ctx.scope({"status": {"$in": ["requested", "approved", "in_transit"]}}))

    by_warehouse = []
    for warehouse in warehouses:
        wb = [b for b in balances if b["warehouse_id"] == warehouse["id"]]
        by_warehouse.append({
            "warehouse_id": warehouse["id"],
            "name": warehouse.get("name"),
            "code": warehouse.get("code"),
            "on_hand": _sum(wb, "quantity_on_hand"),
            "available": _sum(wb, "quantity_available"),
            "value": _sum(wb, "total_value"),
        })

    ledger = await store.find_many("stock_ledger", ctx.scope(), sort=[("created_at", -1)], limit=10)
    audit = await store.find_many("audit_logs", ctx.scope(), sort=[("created_at", -1)], limit=10)

    return {
        "kpis": {
            "total_products": len(products),
            "total_warehouses": len(warehouses),
            "inventory_value": total_value,
            "total_on_hand": total_on_hand,
            "total_available": total_available,
            "low_stock_count": len(low_stock),
            "open_orders": len(open_orders),
            "open_order_value": _sum(open_orders, "total_amount"),
            "pending_receipts": pending_receipts,
            "pending_putaway": pending_putaway,
            "open_picking_tasks": open_picking,
            "shipments_in_transit": in_transit,
            "open_transfers": open_transfers,
        },
        "stock_by_warehouse": by_warehouse,
        "low_stock_items": [
            {"product_id": p["id"], "sku": p.get("sku"), "name": p.get("name"),
             "available": round(stock_by_product.get(p["id"], 0.0), 4),
             "reorder_point": float(p.get("reorder_point") or 0.0),
             "reorder_quantity": float(p.get("reorder_quantity") or 0.0)}
            for p in low_stock[:20]
        ],
        "recent_movements": ledger,
        "recent_activity": audit,
        "generated_at": datetime.now(timezone.utc),
    }


@router.get("/reports/inventory-value")
async def inventory_value_report(ctx: Context = Depends(require_permission("report:read")),
                                 warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    balances = await ctx.store.find_many("inventory_balances", query)
    products = {p["id"]: p for p in await ctx.store.find_many("products", ctx.scope())}
    warehouses = {w["id"]: w for w in await ctx.store.find_many("warehouses", ctx.scope())}

    items: Dict[str, Dict[str, Any]] = {}
    for balance in balances:
        pid = balance["product_id"]
        bucket = items.setdefault(pid, {
            "product_id": pid, "sku": balance.get("sku"), "product_name": balance.get("product_name"),
            "on_hand": 0.0, "value": 0.0, "locations": 0,
        })
        bucket["on_hand"] += float(balance.get("quantity_on_hand") or 0.0)
        bucket["value"] += float(balance.get("total_value") or 0.0)
        bucket["locations"] += 1

    rows = []
    for bucket in items.values():
        bucket["on_hand"] = round(bucket["on_hand"], 4)
        bucket["value"] = round(bucket["value"], 2)
        bucket["average_cost"] = round(bucket["value"] / bucket["on_hand"], 4) if bucket["on_hand"] else 0.0
        rows.append(bucket)
    rows.sort(key=lambda r: r["value"], reverse=True)

    by_warehouse: Dict[str, Dict[str, Any]] = {}
    for balance in balances:
        wid = balance["warehouse_id"]
        bucket = by_warehouse.setdefault(wid, {
            "warehouse_id": wid, "name": (warehouses.get(wid) or {}).get("name"),
            "on_hand": 0.0, "value": 0.0, "reserved": 0.0,
        })
        bucket["on_hand"] += float(balance.get("quantity_on_hand") or 0.0)
        bucket["value"] += float(balance.get("total_value") or 0.0)
        bucket["reserved"] += float(balance.get("quantity_reserved") or 0.0)

    return {
        "total_value": round(sum(r["value"] for r in rows), 2),
        "total_on_hand": round(sum(r["on_hand"] for r in rows), 4),
        "by_product": rows,
        "by_warehouse": [{**w, "on_hand": round(w["on_hand"], 4), "value": round(w["value"], 2)}
                         for w in by_warehouse.values()],
    }


@router.get("/reports/stock-movements")
async def stock_movement_report(ctx: Context = Depends(require_permission("report:read")),
                                days: int = Query(30, ge=1, le=365),
                                warehouse_id: Optional[str] = None,
                                product_id: Optional[str] = None) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = ctx.scope({"created_at": {"$gte": since}})
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if product_id:
        query["product_id"] = product_id
    entries = await ctx.store.find_many("stock_ledger", query, sort=[("created_at", -1)], limit=2000)

    inbound = sum(float(e["quantity"]) for e in entries if float(e.get("quantity") or 0) > 0)
    outbound = sum(float(e["quantity"]) for e in entries if float(e.get("quantity") or 0) < 0)
    by_type: Dict[str, Dict[str, float]] = {}
    for entry in entries:
        bucket = by_type.setdefault(entry["movement_type"], {"count": 0, "quantity": 0.0})
        bucket["count"] += 1
        bucket["quantity"] += float(entry.get("quantity") or 0.0)
    return {
        "period_days": days,
        "entry_count": len(entries),
        "total_in": round(inbound, 4),
        "total_out": round(outbound, 4),
        "by_movement_type": {k: {**v, "quantity": round(v["quantity"], 4)} for k, v in by_type.items()},
        "entries": entries[:200],
    }


@router.get("/reports/fulfillment")
async def fulfillment_report(ctx: Context = Depends(require_permission("report:read")),
                             days: int = Query(30, ge=1, le=365)) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    orders = await ctx.store.find_many("sales_orders", ctx.scope({"created_at": {"$gte": since}}))
    shipments = await ctx.store.find_many("shipments", ctx.scope({"created_at": {"$gte": since}}))
    status_counts: Dict[str, int] = {}
    for order in orders:
        status_counts[order["status"]] = status_counts.get(order["status"], 0) + 1
    shipped = [o for o in orders if o["status"] == "shipped"]
    return {
        "period_days": days,
        "orders_total": len(orders),
        "orders_shipped": len(shipped),
        "orders_by_status": status_counts,
        "shipments_total": len(shipments),
        "shipments_in_transit": sum(1 for s in shipments if s["status"] == "in_transit"),
        "shipments_delivered": sum(1 for s in shipments if s["status"] == "delivered"),
        "fulfillment_rate": round(len(shipped) / len(orders) * 100, 2) if orders else 0.0,
    }


@router.get("/reports/low-stock")
async def low_stock_report(ctx: Context = Depends(require_permission("report:read")),
                           warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    balances = await ctx.store.find_many("inventory_balances", query)
    products = await ctx.store.find_many("products", ctx.scope({"is_archived": False}))

    available: Dict[str, float] = {}
    for balance in balances:
        available[balance["product_id"]] = available.get(balance["product_id"], 0.0) + float(
            balance.get("quantity_available") or 0.0)

    rows = []
    for product in products:
        point = float(product.get("reorder_point") or 0.0)
        avail = available.get(product["id"], 0.0)
        if point > 0 and avail < point:
            rows.append({
                "product_id": product["id"], "sku": product.get("sku"), "name": product.get("name"),
                "available": round(avail, 4), "reorder_point": point,
                "reorder_quantity": float(product.get("reorder_quantity") or 0.0),
                "shortfall": round(point - avail, 4),
            })
    rows.sort(key=lambda r: r["shortfall"], reverse=True)
    return {"items": rows, "count": len(rows)}
