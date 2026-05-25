from motor.motor_asyncio import AsyncIOMotorClient
from backend.app.config import settings

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_state = Database()

async def connect_to_mongo():
    db_state.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db_state.db = db_state.client[settings.MONGODB_DB_NAME]
    print("Connected to MongoDB.")

async def close_mongo_connection():
    if db_state.client:
        db_state.client.close()
        print("Closed MongoDB connection.")

def get_database():
    return db_state.db
