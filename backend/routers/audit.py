"""Audit log access."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from deps import Context, require_permission
from routers.common import paginated

router = APIRouter(tags=["audit"])


@router.get("/audit-logs")
async def list_audit_logs(ctx: Context = Depends(require_permission("audit:read")),
                          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                          entity_type: Optional[str] = None,
                          action: Optional[str] = None,
                          user_id: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if entity_type:
        query["entity_type"] = entity_type
    if action:
        query["action"] = action
    if user_id:
        query["user_id"] = user_id
    return await paginated(ctx.store, "audit_logs", query, page=page, page_size=page_size,
                           sort=[("created_at", -1)])
