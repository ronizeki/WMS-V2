"""FastAPI dependencies: authentication, tenancy scoping and RBAC."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt

from auth import decode_token
from errors import AuthenticationError, PermissionDeniedError, ValidationError
from store import Store, get_store

bearer_scheme = HTTPBearer(auto_error=False)

PLATFORM_TENANT_HEADER = "X-Tenant-Id"


@dataclass
class Context:
    """Per-request security + tenancy context."""

    user: Dict[str, Any]
    tenant_id: Optional[str]
    store: Store
    request: Optional[Request] = None
    _cache: Dict[str, Any] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        return self.user["id"]

    @property
    def is_platform_admin(self) -> bool:
        return bool(self.user.get("is_platform_admin"))

    @property
    def permissions(self) -> List[str]:
        return list(self.user.get("permissions") or [])

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def require(self, *codes: str) -> None:
        missing = [c for c in codes if c not in self.permissions]
        if missing:
            raise PermissionDeniedError(
                "You do not have permission to perform this action",
                details={"missing_permissions": missing},
            )

    def require_tenant(self) -> str:
        if not self.tenant_id:
            raise ValidationError(
                "A tenant context is required. Provide the X-Tenant-Id header."
            )
        return self.tenant_id

    def scope(self, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return ``query`` constrained to the active tenant (never trust the client)."""
        scoped = dict(query or {})
        scoped["tenant_id"] = self.require_tenant()
        return scoped

    def client_meta(self) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        if self.request is not None:
            meta["ip_address"] = self.request.client.host if self.request.client else None
            meta["user_agent"] = self.request.headers.get("user-agent")
        return meta


async def get_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_tenant_id: Optional[str] = Header(default=None, alias=PLATFORM_TENANT_HEADER),
) -> Context:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Not authenticated")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Session expired, please sign in again")
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid authentication token")

    if payload.get("type") not in (None, "access"):
        raise AuthenticationError("Invalid token type")

    store = get_store()
    user = await store.find_one("users", {"id": payload.get("sub")})
    if not user:
        raise AuthenticationError("User no longer exists")
    if user.get("status") != "active":
        raise AuthenticationError("User account is not active")

    tenant_id = user.get("tenant_id")
    if user.get("is_platform_admin"):
        # Platform admins act on a tenant only when explicitly selected.
        tenant_id = x_tenant_id or None
    elif x_tenant_id and x_tenant_id != user.get("tenant_id"):
        # A tenant user must never be able to impersonate another tenant.
        raise PermissionDeniedError("Cross-tenant access is not permitted")

    return Context(user=user, tenant_id=tenant_id, store=store, request=request)


def require_permission(*codes: str):
    """Dependency factory enforcing that the user holds *all* given permissions."""

    async def _checker(ctx: Context = Depends(get_context)) -> Context:
        ctx.require(*codes)
        return ctx

    return _checker


async def get_store_dep() -> Store:
    return get_store()
