"""Sequential document number generation, scoped per tenant and period."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from store import Store

DEFAULT_PREFIXES = {
    "purchase_order": "PO",
    "goods_receipt": "GRN",
    "putaway": "PUT",
    "sales_order": "SO",
    "picking": "PICK",
    "packing": "PACK",
    "shipment": "SHP",
    "transfer": "TRF",
    "adjustment": "ADJ",
    "cycle_count": "CC",
}


def _period(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m")


async def next_number(store: Store, tenant_id: str, doc_type: str,
                      prefix: Optional[str] = None) -> str:
    """Atomically reserve the next sequence value for a document type."""
    prefix = prefix or DEFAULT_PREFIXES.get(doc_type, doc_type[:3].upper())
    period = _period()
    counter_id = f"{tenant_id}:{doc_type}:{period}"

    # Upsert + increment, then read back the allocated value. The in-memory
    # backend serialises mutations behind a lock; MongoDB guarantees the
    # upsert/increment itself is atomic.
    await store.update_one(
        "counters",
        {"id": counter_id},
        set_fields={"tenant_id": tenant_id, "doc_type": doc_type, "period": period},
        inc_fields={"value": 1},
        upsert=True,
    )
    counter = await store.find_one("counters", {"id": counter_id})
    value = int((counter or {}).get("value", 1))
    return f"{prefix}-{period}-{value:05d}"
