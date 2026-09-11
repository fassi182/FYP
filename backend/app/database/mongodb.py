import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client = AsyncIOMotorClient(MONGODB_URI)

db = client[DATABASE_NAME]


async def check_database_connection():
    await client.admin.command("ping")
    print("MongoDB connection successful")


def get_database():
    return db