"""Domain errors mapped to HTTP responses."""
from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Optional[Any] = None,
                 code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class InsufficientStockError(ConflictError):
    code = "insufficient_stock"


class ConcurrencyConflictError(ConflictError):
    code = "concurrency_conflict"


class TenantIsolationError(AppError):
    status_code = 403
    code = "tenant_isolation"
