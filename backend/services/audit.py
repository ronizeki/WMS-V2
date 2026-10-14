"""Audit trail helper. Every mutating operation records an immutable entry."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models import AuditLog
from store import Store


async def record_audit(
    store: Store,
    *,
    tenant_id: Optional[str],
    user: Optional[Dict[str, Any]] = None,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    description: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=(user or {}).get("id"),
        user_email=(user or {}).get("email"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        before=before,
        after=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    doc = entry.model_dump(mode="python")
    doc["created_at"] = datetime.now(timezone.utc)
    await store.insert_one("audit_logs", doc)
    return doc
