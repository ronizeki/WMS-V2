"""Serialization helpers - never leak secrets to the API layer."""
from __future__ import annotations

from typing import Any, Dict

SENSITIVE_KEYS = {"hashed_password", "password"}


def public(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in SENSITIVE_KEYS}


def public_many(docs) -> list:
    return [public(d) for d in docs]
