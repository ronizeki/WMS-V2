"""Authentication endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import jwt

from auth import create_access_token, create_refresh_token, decode_token, verify_password
from deps import Context, get_context
from errors import AuthenticationError, ValidationError
from serializers import public
from store import get_store

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    email: str
    password: str
    tenant_code: Optional[str] = None


class RefreshPayload(BaseModel):
    refresh_token: str


async def _find_user(email: str, tenant_code: Optional[str]) -> Optional[Dict[str, Any]]:
    store = get_store()
    query: Dict[str, Any] = {"email": email.lower()}
    if tenant_code:
        tenant = await store.find_one("tenants", {"code": tenant_code.upper()})
        if not tenant:
            return None
        query["tenant_id"] = tenant["id"]
    matches = await store.find_many("users", query)
    if not matches:
        return None
    if len(matches) > 1:
        raise ValidationError(
            "This email is registered to multiple organizations. Please supply your tenant code."
        )
    return matches[0]


@router.post("/login")
async def login(payload: LoginPayload) -> Dict[str, Any]:
    user = await _find_user(payload.email, payload.tenant_code)
    if not user or not verify_password(payload.password, user.get("hashed_password")):
        raise AuthenticationError("Invalid email or password")
    if user.get("status") != "active":
        raise AuthenticationError("Your account is not active. Contact your administrator.")

    store = get_store()
    now = datetime.now(timezone.utc)
    await store.update_one("users", {"id": user["id"]}, set_fields={"last_login_at": now})

    token_data = {
        "sub": user["id"],
        "email": user["email"],
        "tenant_id": user.get("tenant_id"),
        "is_platform_admin": bool(user.get("is_platform_admin")),
    }
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token({"sub": user["id"]}),
        "token_type": "bearer",
        "user": public(user),
    }


@router.post("/refresh")
async def refresh(payload: RefreshPayload) -> Dict[str, Any]:
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired refresh token")
    if decoded.get("type") != "refresh":
        raise AuthenticationError("Invalid refresh token")

    store = get_store()
    user = await store.find_one("users", {"id": decoded.get("sub")})
    if not user or user.get("status") != "active":
        raise AuthenticationError("User is not available")

    token_data = {
        "sub": user["id"],
        "email": user["email"],
        "tenant_id": user.get("tenant_id"),
        "is_platform_admin": bool(user.get("is_platform_admin")),
    }
    return {
        "access_token": create_access_token(token_data),
        "token_type": "bearer",
        "user": public(user),
    }


@router.get("/me")
async def me(ctx: Context = Depends(get_context)) -> Dict[str, Any]:
    result = public(ctx.user)
    if ctx.tenant_id:
        tenant = await ctx.store.find_one("tenants", {"id": ctx.tenant_id})
        result["tenant"] = public(tenant) if tenant else None
    return result
