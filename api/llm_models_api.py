"""
LLM model registry endpoints.
"""

from fastapi import HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from api.main import api
from services.auth_middleware import AuthenticatedUser
from services.llm_models import get_supported_models
from services.connection_pool import get_postgres_pool


def _require_system_user(current_user: AuthenticatedUser) -> None:
    if current_user.username != "system":
        raise HTTPException(status_code=403, detail="System user required")


class LlmModelCreateRequest(BaseModel):
    provider: str
    model_name: str
    api_key: str
    is_active: bool = True
    is_default: bool = False


class LlmModelUpdateRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


@api.get("/admin/llm-models")
async def list_llm_models(current_user: AuthenticatedUser, include_inactive: Optional[bool] = False):
    """
    List supported LLM models for dropdowns.
    API keys are never returned.
    """
    try:
        models = get_supported_models(include_inactive=bool(include_inactive))
        sanitized = [
            {
                "model_name": m.get("model_name"),
                "provider": m.get("provider"),
                "is_active": m.get("is_active"),
                "is_default": m.get("is_default"),
            }
            for m in models
        ]
        return {"models": sanitized, "count": len(sanitized)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load LLM models: {exc}")


@api.post("/admin/llm-models")
async def create_llm_model(req: LlmModelCreateRequest, current_user: AuthenticatedUser):
    """
    Create a new LLM model entry (system user only).
    """
    _require_system_user(current_user)
    pool = get_postgres_pool()
    
    def _create_sync():
        with pool.connection() as conn:
            with conn.cursor() as cur:
                if req.is_default:
                    cur.execute("UPDATE llm_models SET is_default = FALSE")
                cur.execute(
                    """
                    INSERT INTO llm_models (provider, model_name, api_key, is_active, is_default)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (req.provider, req.model_name, req.api_key, req.is_active, req.is_default),
                )
    
    try:
        import asyncio
        await asyncio.to_thread(_create_sync)
        return {"status": "created", "model_name": req.model_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create model: {exc}")


@api.put("/admin/llm-models/{model_name}")
async def update_llm_model(model_name: str, req: LlmModelUpdateRequest, current_user: AuthenticatedUser):
    """
    Update an LLM model entry (system user only).
    """
    _require_system_user(current_user)
    pool = get_postgres_pool()
    
    def _update_sync():
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, api_key, is_active, is_default
                    FROM llm_models
                    WHERE model_name = %s
                    """,
                    (model_name,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Model not found")

                provider = req.provider if req.provider is not None else row[0]
                api_key = req.api_key if req.api_key is not None else row[1]
                is_active = req.is_active if req.is_active is not None else row[2]
                is_default = req.is_default if req.is_default is not None else row[3]

                if is_default:
                    cur.execute("UPDATE llm_models SET is_default = FALSE")

                cur.execute(
                    """
                    UPDATE llm_models
                    SET provider = %s,
                        api_key = %s,
                        is_active = %s,
                        is_default = %s,
                        updated_at = NOW()
                    WHERE model_name = %s
                    """,
                    (provider, api_key, is_active, is_default, model_name),
                )
    
    try:
        import asyncio
        await asyncio.to_thread(_update_sync)
        return {"status": "updated", "model_name": model_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update model: {exc}")


@api.delete("/admin/llm-models/{model_name}")
async def delete_llm_model(model_name: str, current_user: AuthenticatedUser):
    """
    Delete an LLM model entry (system user only).
    """
    _require_system_user(current_user)
    pool = get_postgres_pool()
    
    def _delete_sync():
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM llm_models WHERE model_name = %s", (model_name,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        import asyncio
        await asyncio.to_thread(_delete_sync)
        return {"status": "deleted", "model_name": model_name}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {exc}")
