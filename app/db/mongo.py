from pymongo import MongoClient
from pymongo.database import Database
from typing import Optional

from app.core.config import settings


class MongoDB:
    """MongoDB connection manager."""

    client: Optional[MongoClient] = None
    db: Optional[Database] = None

    @classmethod
    def connect(cls) -> None:
        cls.client = MongoClient(settings.mongo_uri)
        cls.db = cls.client[settings.mongo_db_name]
        cls._ensure_indexes()

    @classmethod
    def _ensure_indexes(cls) -> None:
        """Create indexes for query performance and uniqueness constraints."""
        cls.get_collection("extractions").create_index("document_id", unique=True)
        cls.get_collection("actions").create_index("document_id", unique=True)
        cls.get_collection("audits").create_index("document_id", unique=True)
        cls.get_collection("reviews").create_index("document_id", unique=True)
        cls.get_collection("users").create_index("email", unique=True)

    @classmethod
    def disconnect(cls) -> None:
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None

    @classmethod
    def get_db(cls) -> Database:
        if cls.db is None:
            cls.connect()
        return cls.db

    @classmethod
    def get_collection(cls, name: str):
        return cls.get_db()[name]


def get_documents():
    return MongoDB.get_collection("documents")


def get_extractions():
    return MongoDB.get_collection("extractions")


def get_actions():
    return MongoDB.get_collection("actions")


def get_audits():
    return MongoDB.get_collection("audits")


def get_reviews():
    return MongoDB.get_collection("reviews")


def get_users():
    return MongoDB.get_collection("users")