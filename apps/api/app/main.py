import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.research import build_research_graph
from app.core.config import Settings, get_settings
from app.core.security import AccessMiddleware
from app.core.security import router as auth_router
from app.db import build_database
from app.providers.demo import DemoQuoteProvider
from app.providers.public import PublicQuoteProvider
from app.quant.routes import router as quant_router
from app.research_routes import router as research_router
from app.routes import router
from app.services.market import MarketService
from app.services.research_data import bootstrap_demo

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessions = build_database(settings.database_url)
        app.state.sessions = sessions
        app.state.settings = settings
        app.state.research_graph = build_research_graph()
        provider = (
            DemoQuoteProvider()
            if settings.market_provider == "demo"
            else PublicQuoteProvider(settings.public_source, settings.provider_timeout_seconds)
        )
        market = MarketService(
            sessions, provider, settings.refresh_interval_seconds, settings.market_provider
        )
        app.state.market = market
        try:
            # 表结构由 Alembic 管理；没有迁移时启动失败，避免悄悄运行错误的数据库结构。
            # 演示数据不做网络请求；公开行情由独立 worker 异步采集，断网也能启动 API。
            if settings.market_provider == "demo":
                for asset in ("stock", "etf", "index"):
                    market.refresh(asset)
                bootstrap_demo(sessions, settings)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Stock Engine API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(AccessMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "Last-Event-ID"],
        allow_credentials=True,
    )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Request failed: %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "服务暂时不可用，请稍后重试"})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Pydantic 的默认错误含原始 input；设置表单可能含密钥，不能回显请求体。
        if request.url.path.startswith("/api/settings/models"):
            return JSONResponse(
                status_code=422,
                content={"detail": "模型设置格式不正确，请检查地址、模型名称及表单字段"},
            )
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, exc)

    app.include_router(router)
    app.include_router(research_router)
    app.include_router(quant_router)
    app.include_router(auth_router)
    return app


app = create_app()
