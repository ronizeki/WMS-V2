"""Idempotency guard for mutation endpoints.

Clients send an ``Idempotency-Key`` header. The first successful call for a
key stores its response; replays of the same key (same tenant + endpoint)
return the stored response instead of re-executing the operation.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from errors import ConflictError
from store import Store

PROCESSING = "processing"
COMPLETED = "completed"


def hash_payload(payload: Any) -> str:
    import json

    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def run_idempotent(
    store: Store,
    *,
    tenant_id: str,
    key: Optional[str],
    endpoint: str,
    payload: Any,
    handler: Callable[[], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Execute ``handler`` at most once per (tenant, endpoint, key)."""
    if not key:
        return await handler()

    record_id = f"{tenant_id}:{endpoint}:{key}"
    existing = await store.find_one("idempotency_keys", {"id": record_id})
    if existing:
        if existing.get("status") == PROCESSING:
            raise ConflictError(
                "A request with this idempotency key is already being processed",
                code="idempotency_in_progress",
            )
        request_hash = hash_payload(payload)
        if existing.get("request_hash") and existing["request_hash"] != request_hash:
            raise ConflictError(
                "This idempotency key was used with a different request payload",
                code="idempotency_key_reuse",
            )
        return existing.get("response") or {}

    await store.insert_one("idempotency_keys", {
        "id": record_id,
        "tenant_id": tenant_id,
        "key": key,
        "endpoint": endpoint,
        "request_hash": hash_payload(payload),
        "status": PROCESSING,
        "response": None,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
    })

    try:
        result = await handler()
    except Exception:
        # Release the key so the client can retry after fixing the problem.
        await store.delete_one("idempotency_keys", {"id": record_id})
        raise

    await store.update_one(
        "idempotency_keys",
        {"id": record_id},
        set_fields={"status": COMPLETED, "response": result},
    )
    return result
