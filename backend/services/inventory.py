"""Inventory transaction engine.

All stock changes flow through :func:`post_movement`, which:
  * mutates a single per-(warehouse, location, product, batch) balance document,
  * uses optimistic concurrency control (``version``) with retry,
  * refuses to drive stock negative unless the tenant allows it,
  * records an immutable ledger entry with before/after quantities.

Reservations are represented explicitly and always reconcile the invariant:

    quantity_available = quantity_on_hand - quantity_damaged
                         - quantity_quarantine - quantity_reserved
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from errors import (
    ConcurrencyConflictError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from models import InventoryBalance, InventoryReservation, StockLedgerEntry, StockMovementType, utcnow
from store import Store

logger = logging.getLogger(__name__)

EPS = 1e-6
MAX_RETRIES = 8
BALANCES = "inventory_balances"
LEDGER = "stock_ledger"
RESERVATIONS = "inventory_reservations"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _round(value: float) -> float:
    return round(float(value or 0.0), 6)


def balance_id(tenant_id: str, warehouse_id: str, location_id: str,
               product_id: str, batch_number: Optional[str]) -> str:
    return f"{tenant_id}:{warehouse_id}:{location_id}:{product_id}:{batch_number or ''}"


def derived_fields(on_hand: float, reserved: float, damaged: float, quarantine: float,
                   average_cost: float) -> Dict[str, float]:
    on_hand = _round(on_hand)
    reserved = _round(reserved)
    damaged = _round(damaged)
    quarantine = _round(quarantine)
    available = _round(on_hand - damaged - quarantine - reserved)
    return {
        "quantity_on_hand": on_hand,
        "quantity_reserved": reserved,
        "quantity_damaged": damaged,
        "quantity_quarantine": quarantine,
        "quantity_available": available,
        "average_cost": _round(average_cost),
        "total_value": _round(on_hand * average_cost),
    }


async def ensure_balance(
    store: Store,
    *,
    tenant_id: str,
    warehouse_id: str,
    location_id: str,
    product: Dict[str, Any],
    batch_number: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    bid = balance_id(tenant_id, warehouse_id, location_id, product["id"], batch_number)
    existing = await store.find_one(BALANCES, {"id": bid})
    if existing:
        return existing

    balance = InventoryBalance(
        id=bid,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        location_id=location_id,
        product_id=product["id"],
        sku=product.get("sku"),
        product_name=product.get("name"),
        unit=product.get("base_unit", "PCS"),
        batch_number=batch_number,
        expiry_date=expiry_date,
    )
    doc = balance.model_dump(mode="python")
    try:
        await store.insert_one(BALANCES, doc)
    except Exception:  # duplicate created concurrently (unique index on Mongo)
        pass
    found = await store.find_one(BALANCES, {"id": bid})
    if not found:
        raise ConcurrencyConflictError("Could not establish inventory balance")
    return found


async def post_movement(
    store: Store,
    *,
    tenant_id: str,
    warehouse_id: str,
    location_id: str,
    product: Dict[str, Any],
    movement_type: StockMovementType,
    quantity: float,
    unit_cost: float = 0.0,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    reference_number: Optional[str] = None,
    batch_number: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
    allow_negative: bool = False,
    reserved_delta: float = 0.0,
    damaged_delta: float = 0.0,
    quarantine_delta: float = 0.0,
    in_transit_delta: float = 0.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Apply a signed stock movement atomically. Returns (ledger, balance)."""
    if abs(quantity) < EPS and abs(reserved_delta) < EPS and abs(damaged_delta) < EPS \
            and abs(quarantine_delta) < EPS and abs(in_transit_delta) < EPS:
        balance = await ensure_balance(
            store, tenant_id=tenant_id, warehouse_id=warehouse_id,
            location_id=location_id, product=product,
            batch_number=batch_number, expiry_date=expiry_date,
        )
        return {}, balance

    last_error: Optional[Exception] = None
    for _ in range(MAX_RETRIES):
        balance = await ensure_balance(
            store, tenant_id=tenant_id, warehouse_id=warehouse_id,
            location_id=location_id, product=product,
            batch_number=batch_number, expiry_date=expiry_date,
        )
        before = float(balance.get("quantity_on_hand") or 0.0)
        new_on_hand = before + quantity
        if new_on_hand < -EPS and not allow_negative:
            raise InsufficientStockError(
                f"Insufficient stock for {product.get('sku') or product['id']} at the selected location",
                details={
                    "product_id": product["id"],
                    "location_id": location_id,
                    "available_on_hand": before,
                    "requested": quantity,
                },
            )

        new_reserved = float(balance.get("quantity_reserved") or 0.0) + reserved_delta
        new_damaged = float(balance.get("quantity_damaged") or 0.0) + damaged_delta
        new_quarantine = float(balance.get("quantity_quarantine") or 0.0) + quarantine_delta
        new_in_transit = float(balance.get("quantity_in_transit") or 0.0) + in_transit_delta

        if new_reserved < -EPS or new_damaged < -EPS or new_quarantine < -EPS:
            raise ValidationError("Stock status quantities cannot become negative")

        # Weighted-average costing: receipts blend cost, issues keep the average.
        avg_cost = float(balance.get("average_cost") or 0.0)
        if quantity > EPS and unit_cost > 0:
            total_qty = before + quantity
            if total_qty > EPS:
                avg_cost = ((before * avg_cost) + (quantity * unit_cost)) / total_qty
            else:
                avg_cost = unit_cost

        fields = derived_fields(new_on_hand, new_reserved, new_damaged, new_quarantine, avg_cost)
        fields["quantity_in_transit"] = _round(new_in_transit)
        fields["updated_at"] = _now()
        if expiry_date and not balance.get("expiry_date"):
            fields["expiry_date"] = expiry_date

        ok = await store.update_one(
            BALANCES,
            {"id": balance["id"], "version": balance["version"]},
            set_fields=fields,
            inc_fields={"version": 1},
        )
        if ok:
            entry = StockLedgerEntry(
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                location_id=location_id,
                product_id=product["id"],
                sku=product.get("sku"),
                movement_type=movement_type,
                quantity=_round(quantity),
                quantity_before=_round(before),
                quantity_after=_round(new_on_hand),
                unit_cost=_round(avg_cost if quantity > 0 else (unit_cost or avg_cost)),
                total_cost=_round(abs(quantity) * (unit_cost or avg_cost)),
                reference_type=reference_type,
                reference_id=reference_id,
                reference_number=reference_number,
                batch_number=batch_number,
                expiry_date=expiry_date,
                reason=reason,
                notes=notes,
                created_by=created_by,
            )
            doc = entry.model_dump(mode="python")
            await store.insert_one(LEDGER, doc)
            updated = await store.find_one(BALANCES, {"id": balance["id"]})
            return doc, updated or balance

        last_error = ConcurrencyConflictError("Inventory balance was modified concurrently")

    raise last_error or ConcurrencyConflictError("Could not update inventory balance")


async def get_stock_position(store: Store, tenant_id: str, warehouse_id: str,
                             product_id: str, *, location_id: Optional[str] = None) -> Dict[str, float]:
    query: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "warehouse_id": warehouse_id,
        "product_id": product_id,
    }
    if location_id:
        query["location_id"] = location_id
    rows = await store.find_many(BALANCES, query)
    totals = {"on_hand": 0.0, "reserved": 0.0, "available": 0.0,
              "damaged": 0.0, "quarantine": 0.0, "in_transit": 0.0, "value": 0.0}
    for row in rows:
        totals["on_hand"] += float(row.get("quantity_on_hand") or 0.0)
        totals["reserved"] += float(row.get("quantity_reserved") or 0.0)
        totals["available"] += float(row.get("quantity_available") or 0.0)
        totals["damaged"] += float(row.get("quantity_damaged") or 0.0)
        totals["quarantine"] += float(row.get("quantity_quarantine") or 0.0)
        totals["in_transit"] += float(row.get("quantity_in_transit") or 0.0)
        totals["value"] += float(row.get("total_value") or 0.0)
    return {k: _round(v) for k, v in totals.items()}


async def _allocate_from_balances(
    store: Store, *, tenant_id: str, warehouse_id: str, product: Dict[str, Any],
    quantity: float, sales_order_id: Optional[str], sales_order_line_id: Optional[str],
    created_by: Optional[str], preferred_location_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], float]:
    query: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "warehouse_id": warehouse_id,
        "product_id": product["id"],
        "quantity_available": {"$gt": 0},
    }
    if preferred_location_id:
        query["location_id"] = preferred_location_id

    balances = await store.find_many(
        BALANCES, query,
        sort=[("expiry_date", 1), ("created_at", 1)],
    )

    allocations: List[Dict[str, Any]] = []
    remaining = _round(quantity)
    for balance in balances:
        if remaining <= EPS:
            break
        available = float(balance.get("quantity_available") or 0.0)
        if available <= EPS:
            continue
        take = min(available, remaining)

        for _ in range(MAX_RETRIES):
            current = await store.find_one(BALANCES, {"id": balance["id"]})
            if not current:
                take = 0
                break
            available_now = float(current.get("quantity_available") or 0.0)
            if available_now <= EPS:
                take = 0
                break
            take = min(take, available_now)
            new_reserved = float(current.get("quantity_reserved") or 0.0) + take
            new_on_hand = float(current.get("quantity_on_hand") or 0.0)
            fields = derived_fields(new_on_hand, new_reserved,
                                    float(current.get("quantity_damaged") or 0.0),
                                    float(current.get("quantity_quarantine") or 0.0),
                                    float(current.get("average_cost") or 0.0))
            fields["updated_at"] = _now()
            ok = await store.update_one(
                BALANCES,
                {"id": current["id"], "version": current["version"]},
                set_fields=fields,
                inc_fields={"version": 1},
            )
            if ok:
                break
        else:
            raise ConcurrencyConflictError("Could not reserve stock, please retry")

        if take <= EPS:
            continue

        reservation = InventoryReservation(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            location_id=balance["location_id"],
            product_id=product["id"],
            sales_order_id=sales_order_id,
            sales_order_line_id=sales_order_line_id,
            quantity=_round(take),
            status="active",
            created_by=created_by,
        )
        reservation_doc = reservation.model_dump(mode="python")
        await store.insert_one(RESERVATIONS, reservation_doc)
        allocations.append({
            "reservation_id": reservation_doc["id"],
            "balance_id": balance["id"],
            "warehouse_id": warehouse_id,
            "location_id": balance["location_id"],
            "product_id": product["id"],
            "sku": product.get("sku"),
            "quantity": _round(take),
            "batch_number": balance.get("batch_number"),
        })
        remaining = _round(remaining - take)

    return allocations, remaining


async def allocate_stock(
    store: Store, *, tenant_id: str, warehouse_id: str, product: Dict[str, Any],
    quantity: float, sales_order_id: Optional[str] = None,
    sales_order_line_id: Optional[str] = None, created_by: Optional[str] = None,
    preferred_location_id: Optional[str] = None, allow_partial: bool = False,
) -> List[Dict[str, Any]]:
    """Reserve stock for an order, allocating across locations (FEFO/FIFO)."""
    if quantity <= EPS:
        return []
    allocations, remaining = await _allocate_from_balances(
        store, tenant_id=tenant_id, warehouse_id=warehouse_id, product=product,
        quantity=quantity, sales_order_id=sales_order_id,
        sales_order_line_id=sales_order_line_id, created_by=created_by,
        preferred_location_id=preferred_location_id,
    )
    if remaining > EPS and not allow_partial:
        await release_allocations(store, allocations, tenant_id=tenant_id)
        position = await get_stock_position(store, tenant_id, warehouse_id, product["id"])
        raise InsufficientStockError(
            f"Not enough available stock for {product.get('sku') or product['id']}",
            details={"requested": quantity, "available": position["available"]},
        )
    return allocations


async def release_allocations(store: Store, allocations: List[Dict[str, Any]],
                              *, tenant_id: str) -> None:
    for allocation in allocations:
        reservation = await store.find_one(RESERVATIONS, {"id": allocation["reservation_id"]})
        if not reservation or reservation.get("status") != "active":
            continue
        balance = await store.find_one(BALANCES, {"id": allocation["balance_id"]})
        if balance:
            new_reserved = max(0.0, float(balance.get("quantity_reserved") or 0.0) - float(allocation["quantity"]))
            fields = derived_fields(
                float(balance.get("quantity_on_hand") or 0.0), new_reserved,
                float(balance.get("quantity_damaged") or 0.0),
                float(balance.get("quantity_quarantine") or 0.0),
                float(balance.get("average_cost") or 0.0),
            )
            fields["updated_at"] = _now()
            await store.update_one(
                BALANCES, {"id": balance["id"], "version": balance["version"]},
                set_fields=fields, inc_fields={"version": 1},
            )
        await store.update_one(
            RESERVATIONS, {"id": reservation["id"]},
            set_fields={"status": "released", "updated_at": _now()},
        )


async def mark_allocations_consumed(store: Store, allocations: List[Dict[str, Any]]) -> None:
    for allocation in allocations:
        await store.update_one(
            RESERVATIONS, {"id": allocation["reservation_id"]},
            set_fields={"status": "consumed", "updated_at": _now()},
        )


async def count_variance(store: Store, tenant_id: str, warehouse_id: str,
                         location_id: str, product_id: str) -> float:
    position = await get_stock_position(store, tenant_id, warehouse_id, product_id,
                                        location_id=location_id)
    return position["on_hand"]
