"""
Storage abstraction for StockPilot WMS.

Provides a small, async, document-store interface with two backends:

* ``MongoStore``  - real persistence via MongoDB (Motor). Used in production
  or whenever a MongoDB instance is reachable.
* ``MemoryStore`` - a fully functional in-process backend used for local
  development, tests and environments where MongoDB is not available. It
  implements the same query/update semantics (a documented subset) and adds
  proper concurrency control so atomic inventory operations behave exactly
  like they do against MongoDB.

The service layer only talks to this interface, so switching backends never
requires code changes elsewhere.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query helpers (shared semantics for both backends)
# ---------------------------------------------------------------------------

_OPERATORS = {"$in", "$nin", "$ne", "$eq", "$gt", "$gte", "$lt", "$lte", "$exists", "$regex", "$all"}


def _get_path(doc: Dict[str, Any], path: str) -> Any:
    """Resolve a dotted path against a document."""
    current: Any = doc
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, (list, tuple)):
            # support list-of-dicts style: treat as "any"
            return [ _get_path(item, part) if isinstance(item, dict) else None for item in current ]
        else:
            return None
    return current


def _as_utc(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, datetime) or isinstance(b, datetime):
        return _as_utc(a) == _as_utc(b)
    return a == b


def _match_field(value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and any(k in _OPERATORS for k in condition):
        for op, operand in condition.items():
            if op == "$eq":
                if not _eq(value, operand):
                    return False
            elif op == "$ne":
                if _eq(value, operand):
                    return False
            elif op == "$in":
                if not any(_eq(value, item) for item in operand):
                    return False
            elif op == "$nin":
                if any(_eq(value, item) for item in operand):
                    return False
            elif op == "$gt":
                if value is None or not value > operand:
                    return False
            elif op == "$gte":
                if value is None or not value >= operand:
                    return False
            elif op == "$lt":
                if value is None or not value < operand:
                    return False
            elif op == "$lte":
                if value is None or not value <= operand:
                    return False
            elif op == "$exists":
                exists = value is not None
                if bool(operand) != exists:
                    return False
            elif op == "$regex":
                if value is None:
                    return False
                flags = re.IGNORECASE if condition.get("$options", "").find("i") >= 0 else 0
                if not re.search(operand, str(value), flags):
                    return False
            elif op == "$all":
                if not isinstance(value, (list, tuple)):
                    return False
                if not all(any(_eq(v, o) for v in value) for o in operand):
                    return False
        return True
    return _eq(value, condition)


def _match(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    if not query:
        return True
    for key, condition in query.items():
        if key == "$or":
            if not any(_match(doc, sub) for sub in condition):
                return False
            continue
        if key == "$and":
            if not all(_match(doc, sub) for sub in condition):
                return False
            continue
        value = _get_path(doc, key)
        if isinstance(value, list) and not isinstance(condition, dict):
            # array field matched against a scalar -> membership
            if not any(_eq(v, condition) for v in value):
                return False
            continue
        if not _match_field(value, condition):
            return False
    return True


def _sort_key(doc: Dict[str, Any], field: str) -> Tuple[int, Any]:
    value = _get_path(doc, field)
    # None should sort last for descending and first for ascending consistently
    if value is None:
        return (1, "")
    return (0, value)


def _apply_update(doc: Dict[str, Any], set_fields: Optional[Dict[str, Any]],
                  inc_fields: Optional[Dict[str, Any]]) -> None:
    for key, value in (set_fields or {}).items():
        _set_path(doc, key, value)
    for key, value in (inc_fields or {}).items():
        existing = _get_path(doc, key) or 0
        _set_path(doc, key, existing + value)


def _set_path(doc: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = doc
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class Store:
    """Abstract async document store."""

    backend_name = "abstract"

    async def insert_one(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def find_many(self, collection: str, query: Optional[Dict[str, Any]] = None,
                        sort: Optional[Sequence[Tuple[str, int]]] = None,
                        skip: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        raise NotImplementedError

    async def update_one(self, collection: str, query: Dict[str, Any],
                         set_fields: Optional[Dict[str, Any]] = None,
                         inc_fields: Optional[Dict[str, Any]] = None,
                         upsert: bool = False) -> bool:
        raise NotImplementedError

    async def replace_one(self, collection: str, query: Dict[str, Any],
                          doc: Dict[str, Any], upsert: bool = False) -> bool:
        raise NotImplementedError

    async def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        raise NotImplementedError

    async def delete_many(self, collection: str, query: Dict[str, Any]) -> int:
        raise NotImplementedError

    async def distinct(self, collection: str, field: str, query: Optional[Dict[str, Any]] = None) -> List[Any]:
        raise NotImplementedError

    async def ping(self) -> bool:
        return True

    async def ensure_indexes(self) -> None:
        return None

    async def clear_all(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------

class MemoryStore(Store):
    """In-process backend with Mongo-like semantics.

    A single lock guards all mutations so that read-modify-write sequences
    (e.g. conditional inventory updates) are atomic with respect to each
    other, mirroring MongoDB's document-level atomicity guarantees.
    """

    backend_name = "memory"

    def __init__(self) -> None:
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    def _coll(self, collection: str) -> List[Dict[str, Any]]:
        return self._data.setdefault(collection, [])

    async def insert_one(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            stored = copy.deepcopy(doc)
            coll = self._coll(collection)
            # "id" behaves as the primary key: inserting a duplicate is a no-op
            # so that get-or-create sequences stay race-free.
            doc_id = stored.get("id")
            if doc_id is not None:
                for existing in coll:
                    if existing.get("id") == doc_id:
                        return copy.deepcopy(existing)
            coll.append(stored)
            return copy.deepcopy(stored)

    async def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self._lock:
            for doc in self._coll(collection):
                if _match(doc, query):
                    return copy.deepcopy(doc)
        return None

    async def find_many(self, collection: str, query: Optional[Dict[str, Any]] = None,
                        sort: Optional[Sequence[Tuple[str, int]]] = None,
                        skip: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
        query = query or {}
        async with self._lock:
            results = [copy.deepcopy(d) for d in self._coll(collection) if _match(d, query)]
        if sort:
            for field, direction in reversed(list(sort)):
                reverse = direction == -1
                results.sort(key=lambda d: _sort_key(d, field), reverse=reverse)
        if skip:
            results = results[skip:]
        if limit:
            results = results[:limit]
        return results

    async def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        query = query or {}
        async with self._lock:
            return sum(1 for d in self._coll(collection) if _match(d, query))

    async def update_one(self, collection: str, query: Dict[str, Any],
                         set_fields: Optional[Dict[str, Any]] = None,
                         inc_fields: Optional[Dict[str, Any]] = None,
                         upsert: bool = False) -> bool:
        async with self._lock:
            for doc in self._coll(collection):
                if _match(doc, query):
                    _apply_update(doc, set_fields, inc_fields)
                    return True
            if upsert:
                new_doc: Dict[str, Any] = {}
                for key, value in query.items():
                    if not key.startswith("$") and not isinstance(value, dict):
                        _set_path(new_doc, key, value)
                _apply_update(new_doc, set_fields, inc_fields)
                self._coll(collection).append(new_doc)
                return True
        return False

    async def replace_one(self, collection: str, query: Dict[str, Any],
                          doc: Dict[str, Any], upsert: bool = False) -> bool:
        async with self._lock:
            coll = self._coll(collection)
            for index, current in enumerate(coll):
                if _match(current, query):
                    coll[index] = copy.deepcopy(doc)
                    return True
            if upsert:
                coll.append(copy.deepcopy(doc))
                return True
        return False

    async def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        async with self._lock:
            coll = self._coll(collection)
            for index, current in enumerate(coll):
                if _match(current, query):
                    coll.pop(index)
                    return True
        return False

    async def delete_many(self, collection: str, query: Dict[str, Any]) -> int:
        async with self._lock:
            coll = self._coll(collection)
            keep = [d for d in coll if not _match(d, query)]
            removed = len(coll) - len(keep)
            self._data[collection] = keep
            return removed

    async def distinct(self, collection: str, field: str, query: Optional[Dict[str, Any]] = None) -> List[Any]:
        rows = await self.find_many(collection, query)
        seen = []
        for row in rows:
            value = _get_path(row, field)
            if value not in seen:
                seen.append(value)
        return seen

    async def clear_all(self) -> None:
        async with self._lock:
            self._data = {}


# ---------------------------------------------------------------------------
# MongoDB backend
# ---------------------------------------------------------------------------

class MongoStore(Store):
    backend_name = "mongodb"

    def __init__(self, database) -> None:
        self._db = database

    def _coll(self, collection: str):
        return self._db[collection]

    async def insert_one(self, collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        stored = copy.deepcopy(doc)
        stored.pop("_id", None)
        await self._coll(collection).insert_one(stored)
        return stored

    async def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doc = await self._coll(collection).find_one(query, {"_id": 0})
        return doc

    async def find_many(self, collection: str, query: Optional[Dict[str, Any]] = None,
                        sort: Optional[Sequence[Tuple[str, int]]] = None,
                        skip: int = 0, limit: int = 0) -> List[Dict[str, Any]]:
        cursor = self._coll(collection).find(query or {}, {"_id": 0})
        if sort:
            cursor = cursor.sort(list(sort))
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit or None)

    async def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        return await self._coll(collection).count_documents(query or {})

    async def update_one(self, collection: str, query: Dict[str, Any],
                         set_fields: Optional[Dict[str, Any]] = None,
                         inc_fields: Optional[Dict[str, Any]] = None,
                         upsert: bool = False) -> bool:
        update: Dict[str, Any] = {}
        if set_fields:
            update["$set"] = set_fields
        if inc_fields:
            update["$inc"] = inc_fields
        if not update:
            return False
        result = await self._coll(collection).update_one(query, update, upsert=upsert)
        return bool(result.matched_count or result.upserted_id)

    async def replace_one(self, collection: str, query: Dict[str, Any],
                          doc: Dict[str, Any], upsert: bool = False) -> bool:
        stored = copy.deepcopy(doc)
        stored.pop("_id", None)
        result = await self._coll(collection).replace_one(query, stored, upsert=upsert)
        return bool(result.matched_count or result.upserted_id)

    async def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        result = await self._coll(collection).delete_one(query)
        return bool(result.deleted_count)

    async def delete_many(self, collection: str, query: Dict[str, Any]) -> int:
        result = await self._coll(collection).delete_many(query)
        return int(result.deleted_count)

    async def distinct(self, collection: str, field: str, query: Optional[Dict[str, Any]] = None) -> List[Any]:
        return await self._coll(collection).distinct(field, query or {})

    async def ping(self) -> bool:
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False

    async def ensure_indexes(self) -> None:
        try:
            await self._db.tenants.create_index("code", unique=True)
            await self._db.users.create_index([("tenant_id", 1), ("email", 1)], unique=True)
            await self._db.inventory_balances.create_index(
                [("tenant_id", 1), ("warehouse_id", 1), ("location_id", 1),
                 ("product_id", 1), ("batch_number", 1)], unique=True)
            await self._db.stock_ledger.create_index([("tenant_id", 1), ("product_id", 1), ("created_at", -1)])
            await self._db.idempotency_keys.create_index([("tenant_id", 1), ("key", 1)], unique=True)
            await self._db.audit_logs.create_index([("tenant_id", 1), ("created_at", -1)])
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("ensure_indexes failed: %s", exc)

    async def clear_all(self) -> None:
        for name in await self._db.list_collection_names():
            await self._db[name].delete_many({})


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_store: Optional[Store] = None


def set_store(store: Store) -> None:
    global _store
    _store = store


def get_store() -> Store:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


async def init_store(mongo_database=None) -> Store:
    """Initialise the active store.

    Prefers MongoDB when a database handle is provided *and* reachable,
    otherwise falls back to the in-memory backend so the API is always usable.
    """
    global _store
    if mongo_database is not None:
        candidate = MongoStore(mongo_database)
        if await candidate.ping():
            await candidate.ensure_indexes()
            _store = candidate
            logger.info("Storage backend: MongoDB")
            return _store
        logger.warning("MongoDB not reachable - falling back to in-memory storage")
    _store = MemoryStore()
    logger.info("Storage backend: in-memory")
    return _store
