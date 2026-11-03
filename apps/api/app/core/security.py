import hashlib
import hmac
import secrets
import time
from collections import OrderedDict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, SecretStr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import Settings

router = APIRouter(prefix="/api/auth")


def authenticated(request: Request, settings: Settings) -> bool:
    if not settings.app_api_key:
        return True
    secret = settings.app_api_key.get_secret_value()
    bearer = request.headers.get("Authorization", "")
    if bearer.startswith("Bearer ") and secrets.compare_digest(
        bearer[7:].encode(), secret.encode()
    ):
        return True
    token = request.cookies.get("stock_session", "")
    try:
        payload, signature = token.rsplit(".", 1)
        expires, _ = payload.split(":", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return int(expires) > time.time() and secrets.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


class AccessMiddleware(BaseHTTPMiddleware):
    """单 API 进程的有界限流；多实例部署需在网关或 Redis 统一执行。"""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.requests = OrderedDict()

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        public = path in {"/api/health", "/api/auth/status", "/api/auth/login"}
        if not public and not authenticated(request, self.settings):
            return JSONResponse({"detail": "请先输入应用访问密钥"}, status_code=401)
        # 使用连接地址，不信任用户自行传入的 X-Forwarded-For。
        client = request.client.host if request.client else "unknown"
        bucket = (
            "login"
            if path == "/api/auth/login"
            else "write"
            if request.method == "POST"
            else "read"
        )
        key, now = (client, bucket), time.monotonic()
        queue = self.requests.setdefault(key, deque())
        self.requests.move_to_end(key)
        while queue and queue[0] <= now - 60:
            queue.popleft()
        limit = {"login": 10, "write": 30, "read": 180}[bucket]
        if len(queue) >= limit:
            return JSONResponse(
                {"detail": "请求过于频繁，请稍后重试"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        queue.append(now)
        if len(self.requests) > 4096:
            self.requests.popitem(last=False)
        if request.method == "POST" and request.headers.get("origin"):
            if request.headers["origin"] not in self.settings.cors_origins:
                return JSONResponse({"detail": "请求来源不允许"}, status_code=403)
        return await call_next(request)


class LoginRequest(BaseModel):
    key: SecretStr


@router.get("/status")
def status(request: Request):
    settings = request.app.state.settings
    return {
        "required": bool(settings.app_api_key),
        "authenticated": authenticated(request, settings),
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    settings = request.app.state.settings
    if not settings.app_api_key:
        return {"authenticated": True}
    secret = settings.app_api_key.get_secret_value()
    if not secrets.compare_digest(payload.key.get_secret_value().encode(), secret.encode()):
        raise HTTPException(401, "应用访问密钥不正确")
    message = f"{int(time.time()) + 28800}:{secrets.token_hex(16)}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    response.set_cookie(
        "stock_session",
        f"{message}.{signature}",
        max_age=28800,
        httponly=True,
        samesite="strict",
        secure=settings.app_environment == "production",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("stock_session")
    return {"authenticated": False}
