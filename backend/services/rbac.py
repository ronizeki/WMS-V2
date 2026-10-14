"""Role / permission resolution."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models import (
    ALL_PERMISSIONS,
    DEFAULT_ROLE_NAMES,
    DEFAULT_ROLE_PERMISSIONS,
    RoleCode,
    TENANT_ROLE_CODES,
    Role,
)
from store import Store


def role_id(tenant_id: Optional[str], code: str) -> str:
    return f"{tenant_id or 'platform'}:{code}"


async def ensure_tenant_roles(store: Store, tenant_id: str) -> Dict[str, Dict[str, Any]]:
    """Create the six default tenant roles if they are missing."""
    roles: Dict[str, Dict[str, Any]] = {}
    for code in TENANT_ROLE_CODES:
        rid = role_id(tenant_id, code)
        existing = await store.find_one("roles", {"id": rid})
        if existing:
            roles[code] = existing
            continue
        role = Role(
            id=rid,
            tenant_id=tenant_id,
            code=code,
            name=DEFAULT_ROLE_NAMES[code],
            permissions=list(DEFAULT_ROLE_PERMISSIONS[code]),
            is_system=True,
            description=f"Default {DEFAULT_ROLE_NAMES[code]} role",
        )
        doc = role.model_dump(mode="python")
        await store.insert_one("roles", doc)
        roles[code] = doc
    return roles


async def ensure_platform_roles(store: Store) -> Dict[str, Dict[str, Any]]:
    rid = role_id(None, RoleCode.PLATFORM_ADMIN.value)
    existing = await store.find_one("roles", {"id": rid})
    if existing:
        return {RoleCode.PLATFORM_ADMIN.value: existing}
    role = Role(
        id=rid,
        tenant_id=None,
        code=RoleCode.PLATFORM_ADMIN.value,
        name=DEFAULT_ROLE_NAMES[RoleCode.PLATFORM_ADMIN.value],
        permissions=list(ALL_PERMISSIONS),
        is_system=True,
        description="Platform-wide administrator",
    )
    doc = role.model_dump(mode="python")
    await store.insert_one("roles", doc)
    return {RoleCode.PLATFORM_ADMIN.value: doc}


async def resolve_roles(
    store: Store, *, tenant_id: Optional[str],
    role_codes: Optional[List[str]] = None,
    role_ids: Optional[List[str]] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """Return (role_ids, role_codes, permissions) for a user assignment."""
    resolved: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for rid in role_ids or []:
        role = await store.find_one("roles", {"id": rid})
        if not role:
            continue
        if role.get("tenant_id") not in (None, tenant_id):
            # never allow assigning a role that belongs to another tenant
            continue
        if role["id"] not in seen_ids:
            resolved.append(role)
            seen_ids.add(role["id"])

    for code in role_codes or []:
        query: Dict[str, Any] = {"code": code}
        if tenant_id:
            query["tenant_id"] = tenant_id
        else:
            query["tenant_id"] = None
        role = await store.find_one("roles", query)
        if role and role["id"] not in seen_ids:
            resolved.append(role)
            seen_ids.add(role["id"])

    permissions: List[str] = []
    codes: List[str] = []
    ids: List[str] = []
    for role in resolved:
        ids.append(role["id"])
        codes.append(role["code"])
        for permission in role.get("permissions") or []:
            if permission not in permissions:
                permissions.append(permission)

    return ids, codes, sorted(permissions)
