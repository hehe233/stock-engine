from fastapi import APIRouter, Request
from sqlalchemy import text

from app.http.dependencies import SessionDep
from app.model_settings.service import (
    effective_settings,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request, session: SessionDep):
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "data_mode": request.app.state.settings.market_provider,
        "version": "0.2.0",
    }


@router.get("/config")
def config(request: Request, session: SessionDep):
    settings = effective_settings(session, request.app.state.settings)
    return {
        "market_provider": settings.market_provider,
        "refresh_interval_seconds": settings.refresh_interval_seconds,
        "api_configured": bool(settings.llm_api_key and settings.api_models),
        "api_models": settings.api_models,
        "default_model": settings.llm_model,
        "ollama_model": settings.ollama_model,
    }
