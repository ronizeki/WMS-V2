from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None

async def connect_to_mongo():
    global client, db
    try:
        client = AsyncIOMotorClient(settings.mongo_url)
        db = client[settings.db_name]
        try:
            await db.command("ping")
            logger.info(f"Connected to MongoDB: {settings.db_name}")
        except Exception as e:
            logger.warning(f"Could not ping MongoDB (may not be running): {e}")
            logger.info(f"Connected to MongoDB client: {settings.db_name}")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    global client
    if client:
        client.close()
        logger.info("Disconnected from MongoDB")

async def get_database():
    return db