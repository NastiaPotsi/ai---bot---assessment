from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from app.core.config import Settings


async def create_mongo_database(
    settings: Settings,
) -> tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
    database = client[settings.mongo_database]
    try:
        await database.sessions.create_index("session_id", unique=True)
        await database.requests.create_index("request_id", unique=True)
        await database.requests.create_index("duplicate_key")
    except PyMongoError:
        # Let the app start so health checks and route-level 503s stay available.
        pass
    return client, database
