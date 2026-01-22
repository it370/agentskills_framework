"""
LLM model registry backed by database.

Provides cached access to supported model list and API keys.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from services.connection_pool import get_postgres_pool
from log_stream import emit_log

_CACHE_TTL_SECONDS = 60
_model_cache: Dict[str, object] = {"fetched_at": 0.0, "models": []}


def _fetch_models_from_db() -> List[Dict[str, object]]:
    pool = get_postgres_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT model_name, provider, api_key, is_active, is_default
                FROM llm_models
                ORDER BY model_name ASC
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "model_name": row[0],
                    "provider": row[1],
                    "api_key": row[2],
                    "is_active": bool(row[3]),
                    "is_default": bool(row[4]),
                }
                for row in rows
            ]
    finally:
        pool.putconn(conn)


def _refresh_cache_if_needed() -> None:
    now = time.time()
    fetched_at = float(_model_cache.get("fetched_at") or 0.0)
    if (now - fetched_at) < _CACHE_TTL_SECONDS:
        return
    try:
        _model_cache["models"] = _fetch_models_from_db()
        _model_cache["fetched_at"] = now
    except Exception as exc:
        emit_log(f"[LLM_MODELS] Warning: Failed to refresh model list: {exc}")


def get_supported_models(include_inactive: bool = False) -> List[Dict[str, object]]:
    _refresh_cache_if_needed()
    models = list(_model_cache.get("models") or [])
    if include_inactive:
        return models
    return [m for m in models if m.get("is_active")]


def get_model_config(model_name: str) -> Optional[Dict[str, object]]:
    if not model_name:
        return None
    models = get_supported_models(include_inactive=False)
    for model in models:
        if model.get("model_name") == model_name:
            return model
    return None


def get_default_model() -> Optional[str]:
    models = get_supported_models(include_inactive=False)
    for model in models:
        if model.get("is_default"):
            return str(model.get("model_name"))
    return None
