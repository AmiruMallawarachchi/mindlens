from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from app.config import settings

class Database:
    client: Optional[AsyncIOMotorClient] = None
    
db = Database()

async def connect_db():
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    print(f"Connected to MongoDB: {settings.mongodb_db_name}")
    
    database = db.client[settings.mongodb_db_name]
    
    await database.users.create_index("email", unique=True)
    await database.sessions.create_index("user_id")
    await database.sessions.create_index("created_at")
    await database.mood_logs.create_index([("user_id", 1), ("timestamp", -1)])
    await database.safety_events.create_index("timestamp")
    
    print("Database indexes created")

async def close_db():
    if db.client:
        db.client.close()
        print("MongoDB connection closed")

def get_database():
    if db.client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db.client[settings.mongodb_db_name]