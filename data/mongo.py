from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from env_loader import load_env_once
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Load env files once at import; shared utility for reuse across modules.
_loaded_paths = load_env_once(_PROJECT_ROOT)
mongo_db = os.getenv("MONGODB_DB", "").strip()
print(f"[mongo.py] env loaded: MONGODB_DB={'(empty)' if not mongo_db else mongo_db}")


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str


@lru_cache(maxsize=1)
def _get_settings() -> MongoSettings:
    """Return Mongo settings pulled from environment variables."""

    return MongoSettings(
        uri=_get_env_value("MONGODB_URI", "mongodb://localhost:27017"),
        db_name=_get_env_value("MONGODB_DB", "clearstar"),
    )


def _get_env_value(key: str, default: str) -> str:
    """Fetch an env var and fall back when unset or blank."""

    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip()


@lru_cache(maxsize=1)
def _get_client() -> MongoClient[Any]:
    """Return a singleton MongoDB client configured from env settings."""

    settings = _get_settings()
    return MongoClient(settings.uri)


def get_client() -> MongoClient[Any]:
    """Public accessor for the shared Mongo client instance."""

    return _get_client()


def get_db() -> Database[Any]:
    """Return the configured MongoDB database."""

    settings = _get_settings()
    return _get_client()[settings.db_name]


def get_collection(name: str) -> Collection[Any]:
    """Convenience helper to retrieve a collection by name."""

    if not name:
        raise ValueError("Collection name must be provided")

    return get_db()[name]