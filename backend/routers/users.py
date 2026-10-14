"""Tenant users, roles and permissions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr

from auth import get_password_hash
from deps import Context, get_context, require_permission
from errors import ConflictError, NotFoundError, ValidationError
from models import ALL_PERMISSIONS, PERMISSION_CATALOG, Role, RoleCode, UserStatus, new_id, utcnow
from routers.common import clean, paginated
from serializers import public
from services.audit import record_audit
from services.rbac import ensure_tenant_roles, resolve_roles

router = APIRouter(tags=["users"])


class RolePayload(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = []


class UserPayload(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = None
    role_codes: List[str] = []
    role_ids: List[str] = []
    warehouse_ids: List[str] = []
    phone: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE


class UserUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[UserStatus] = None
    role_codes: Optional[List[str]] = None
    role_ids: Optional[List[str]] = None
    warehouse_ids: Optional[List[str]] = None


@router.get("/permissions")
async def list_permissions(ctx: Context = Depends(get_context)) -> Dict[str, Any]:
    categories: Dict[str, List[Dict[str, str]]] = {}
    for permission in PERMISSION_CATALOG:
        categories.setdefault(permission["category"], []).append(permission)
    return {"permissions": PERMISSION_CATALOG, "by_category": categories}


@router.get("/roles")
async def list_roles(ctx: Context = Depends(require_permission("role:read"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await ensure_tenant_roles(ctx.store, tenant_id)
    roles = await ctx.store.find_many("roles", {"tenant_id": tenant_id}, sort=[("code", 1)])
    return {"items": roles}


@router.post("/roles", status_code=201)
async def create_role(payload: RolePayload,
                      ctx: Context = Depends(require_permission("role:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await ensure_tenant_roles(ctx.store, tenant_id)
    invalid = [p for p in payload.permissions if p not in ALL_PERMISSIONS]
    if invalid:
        raise ValidationError("Unknown permission code(s)", details=invalid)
    if await ctx.store.find_one("roles", {"tenant_id": tenant_id, "code": payload.code}):
        raise ConflictError("A role with this code already exists")
    role = Role(tenant_id=tenant_id, code=payload.code, name=payload.name,
                description=payload.description, permissions=sorted(set(payload.permissions)))
    doc = role.model_dump(mode="python")
    await ctx.store.insert_one("roles", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="role", entity_id=doc["id"], after=doc, **ctx.client_meta())
    return doc


@router.patch("/roles/{role_id}")
async def update_role(role_id: str, payload: RolePayload,
                      ctx: Context = Depends(require_permission("role:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    role = await ctx.store.find_one("roles", {"id": role_id, "tenant_id": tenant_id})
    if not role:
        raise NotFoundError("Role not found")
    invalid = [p for p in payload.permissions if p not in ALL_PERMISSIONS]
    if invalid:
        raise ValidationError("Unknown permission code(s)", details=invalid)
    updates = {
        "name": payload.name,
        "description": payload.description,
        "permissions": sorted(set(payload.permissions)),
        "updated_at": utcnow(),
    }
    await ctx.store.update_one("roles", {"id": role_id, "tenant_id": tenant_id}, set_fields=updates)
    await sync_role_permissions(ctx.store, tenant_id, role_id)
    return await ctx.store.find_one("roles", {"id": role_id})


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(role_id: str,
                      ctx: Context = Depends(require_permission("role:write"))) -> None:
    tenant_id = ctx.require_tenant()
    role = await ctx.store.find_one("roles", {"id": role_id, "tenant_id": tenant_id})
    if not role:
        raise NotFoundError("Role not found")
    if role.get("is_system"):
        raise ValidationError("System roles cannot be deleted")
    await ctx.store.delete_one("roles", {"id": role_id, "tenant_id": tenant_id})


async def sync_role_permissions(store, tenant_id: str, role_id: str) -> None:
    """Refresh denormalized permissions on every user holding the role."""
    users = await store.find_many("users", {"tenant_id": tenant_id, "role_ids": role_id})
    for user in users:
        _, codes, permissions = await resolve_roles(
            store, tenant_id=tenant_id, role_ids=user.get("role_ids") or [],
            role_codes=user.get("role_codes") or [],
        )
        await store.update_one("users", {"id": user["id"]},
                               set_fields={"permissions": permissions, "role_codes": codes})


@router.get("/users")
async def list_users(ctx: Context = Depends(require_permission("user:read")),
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                     search: Optional[str] = None,
                     status: Optional[UserStatus] = None) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    query: Dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        query["status"] = status.value
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    result = await paginated(ctx.store, "users", query, page=page, page_size=page_size)
    result["items"] = [public(u) for u in result["items"]]
    return result


@router.post("/users", status_code=201)
async def create_user(payload: UserPayload,
                      ctx: Context = Depends(require_permission("user:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await ensure_tenant_roles(ctx.store, tenant_id)
    email = payload.email.lower()
    if await ctx.store.find_one("users", {"tenant_id": tenant_id, "email": email}):
        raise ConflictError("A user with this email already exists in this organization")
    if not payload.password:
        raise ValidationError("A password is required when creating a user")

    role_ids, role_codes, permissions = await resolve_roles(
        ctx.store, tenant_id=tenant_id,
        role_codes=payload.role_codes or [RoleCode.WAREHOUSE_OPERATOR.value],
        role_ids=payload.role_ids,
    )
    user = {
        "id": new_id(),
        "tenant_id": tenant_id,
        "email": email,
        "full_name": payload.full_name,
        "hashed_password": get_password_hash(payload.password),
        "status": payload.status.value,
        "role_ids": role_ids,
        "role_codes": role_codes,
        "permissions": permissions,
        "phone": payload.phone,
        "warehouse_ids": payload.warehouse_ids or [],
        "is_platform_admin": False,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    await ctx.store.insert_one("users", user)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="user", entity_id=user["id"],
                       after={"email": email, "role_codes": role_codes}, **ctx.client_meta())
    return public(user)


@router.get("/users/{user_id}")
async def get_user(user_id: str, ctx: Context = Depends(require_permission("user:read"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    user = await ctx.store.find_one("users", {"id": user_id, "tenant_id": tenant_id})
    if not user:
        raise NotFoundError("User not found")
    return public(user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdatePayload,
                      ctx: Context = Depends(require_permission("user:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    user = await ctx.store.find_one("users", {"id": user_id, "tenant_id": tenant_id})
    if not user:
        raise NotFoundError("User not found")

    updates: Dict[str, Any] = {}
    if payload.full_name is not None:
        updates["full_name"] = payload.full_name
    if payload.phone is not None:
        updates["phone"] = payload.phone
    if payload.warehouse_ids is not None:
        updates["warehouse_ids"] = payload.warehouse_ids
    if payload.status is not None:
        updates["status"] = payload.status.value
    if payload.role_codes is not None or payload.role_ids is not None:
        role_ids, role_codes, permissions = await resolve_roles(
            ctx.store, tenant_id=tenant_id,
            role_codes=payload.role_codes if payload.role_codes is not None else user.get("role_codes"),
            role_ids=payload.role_ids if payload.role_ids is not None else user.get("role_ids"),
        )
        updates.update({"role_ids": role_ids, "role_codes": role_codes, "permissions": permissions})
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("users", {"id": user_id, "tenant_id": tenant_id}, set_fields=updates)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="update",
                       entity_type="user", entity_id=user_id, after=updates, **ctx.client_meta())
    return public(await ctx.store.find_one("users", {"id": user_id}))


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, payload: Dict[str, str],
                         ctx: Context = Depends(require_permission("user:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    password = payload.get("password")
    if not password:
        raise ValidationError("A new password is required")
    user = await ctx.store.find_one("users", {"id": user_id, "tenant_id": tenant_id})
    if not user:
        raise NotFoundError("User not found")
    await ctx.store.update_one("users", {"id": user_id},
                               set_fields={"hashed_password": get_password_hash(password),
                                           "updated_at": utcnow()})
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="reset_password",
                       entity_type="user", entity_id=user_id, **ctx.client_meta())
    return {"status": "ok"}


@router.delete("/users/{user_id}", status_code=204)
async def deactivate_user(user_id: str,
                          ctx: Context = Depends(require_permission("user:write"))) -> None:
    tenant_id = ctx.require_tenant()
    if user_id == ctx.user_id:
        raise ValidationError("You cannot deactivate your own account")
    user = await ctx.store.find_one("users", {"id": user_id, "tenant_id": tenant_id})
    if not user:
        raise NotFoundError("User not found")
    await ctx.store.update_one("users", {"id": user_id},
                               set_fields={"status": UserStatus.INACTIVE.value, "updated_at": utcnow()})
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="deactivate",
                       entity_type="user", entity_id=user_id, **ctx.client_meta())
