"""StockPilot WMS API entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI, APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import close_mongo_connection, connect_to_mongo, get_database
from errors import AppError
from store import get_store, init_store

from routers import (
    audit as audit_router,
    auth as auth_router,
    inbound as inbound_router,
    inventory as inventory_router,
    outbound as outbound_router,
    platform as platform_router,
    products as products_router,
    reports as reports_router,
    stocktake as stocktake_router,
    transfers as transfers_router,
    users as users_router,
    warehouses as warehouses_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STARTED_AT: dict = {}


async def _startup() -> None:
    db_handle = None
    if not settings.skip_mongo:
        try:
            await connect_to_mongo()
            db_handle = await get_database()
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("MongoDB connection failed: %s", exc)
    else:
        logger.info("SKIP_MONGO enabled - using in-memory storage")

    store = await init_store(db_handle)

    if settings.demo_data_enabled:
        try:
            from seed import ensure_seed

            await ensure_seed(store)
        except Exception as exc:  # pragma: no cover
            logger.warning("Seeding skipped/failed: %s", exc)


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    app.state.store = get_store()
    logger.info("Application startup completed (storage=%s)", get_store().backend_name)
    yield
    await close_mongo_connection()
    logger.info("Application shutdown completed")


app = FastAPI(
    title="StockPilot WMS API",
    description="Multi-Tenant SaaS Warehouse Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code, "details": exc.details},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(part) for part in error.get("loc", []) if part != "body"),
            "message": error.get("msg"),
            "type": error.get("type"),
        })
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "code": "validation_error", "details": errors},
    )


api_router = APIRouter(prefix=settings.api_v1_str)


@api_router.get("/health")
async def health_check():
    store = get_store()
    return {
        "status": "ok",
        "message": "StockPilot WMS API is running",
        "version": settings.app_version,
        "environment": settings.environment,
        "storage_backend": store.backend_name,
    }


@api_router.get("/health/storage")
async def storage_health():
    store = get_store()
    reachable = await store.ping()
    return {"backend": store.backend_name, "reachable": reachable}


@api_router.get("/")
async def root():
    return {"message": "Welcome to StockPilot WMS API", "docs": "/docs",
            "storage_backend": get_store().backend_name}


for router in (
    auth_router.router,
    platform_router.router,
    users_router.router,
    warehouses_router.router,
    products_router.router,
    inventory_router.router,
    inbound_router.router,
    outbound_router.router,
    transfers_router.router,
    stocktake_router.router,
    reports_router.router,
    audit_router.router,
):
    api_router.include_router(router)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
