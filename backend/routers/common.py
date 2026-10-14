"""Shared helpers for API routers."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from errors import NotFoundError, ValidationError
from store import Store


def pagination_meta(page: int, page_size: int, total: int) -> Dict[str, int]:
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def paginated(store: Store, collection: str, query: Dict[str, Any],
                    *, page: int = 1, page_size: int = 20,
                    sort: Optional[Sequence[Tuple[str, int]]] = None) -> Dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total = await store.count(collection, query)
    items = await store.find_many(
        collection, query, sort=sort or [("created_at", -1)],
        skip=(page - 1) * page_size, limit=page_size,
    )
    return {"items": items, "meta": pagination_meta(page, page_size, total)}


async def get_or_404(store: Store, collection: str, ctx, record_id: str) -> Dict[str, Any]:
    query = ctx.scope({"id": record_id})
    record = await store.find_one(collection, query)
    if not record:
        raise NotFoundError(f"{collection.replace('_', ' ').title()} not found")
    return record


def clean(data: Dict[str, Any], allowed: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Drop None values (and optionally restrict keys) before persisting."""
    result = {k: v for k, v in data.items() if v is not None}
    if allowed is not None:
        result = {k: v for k, v in result.items() if k in allowed}
    return result


def require_fields(data: Dict[str, Any], fields: Sequence[str]) -> None:
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")
