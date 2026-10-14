from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
import logging

from config import settings
from database import connect_to_mongo, close_mongo_connection

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await connect_to_mongo()
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        logger.info("Continuing without MongoDB for now")
    logger.info("Application startup completed")
    yield
    await close_mongo_connection()
    logger.info("Application shutdown completed")

app = FastAPI(
    title="StockPilot WMS API",
    description="Multi-Tenant SaaS Warehouse Management System",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix=settings.api_v1_str)

@api_router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "StockPilot WMS API is running",
        "version": settings.app_version,
        "environment": settings.environment
    }

@api_router.get("/")
async def root():
    return {"message": "Welcome to StockPilot WMS API"}

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)