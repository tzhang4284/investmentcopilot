import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import settings
from .db import engine, init_db
from .routers import chat, insiders, memos, portfolio, stocks, theses
from .services.ai.client import ai_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Investment Copilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    """When API_AUTH_TOKEN is set (production), reject requests that don't
    carry it. The Next.js server-side proxy injects the header after checking
    the user's session, so the browser never sees the token."""
    if settings.api_auth_token and request.url.path != "/api/health":
        header = request.headers.get("authorization", "")
        expected = f"Bearer {settings.api_auth_token}"
        if not hmac.compare_digest(header, expected):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


for router in (portfolio.router, stocks.router, insiders.router, theses.router, chat.router, memos.router):
    app.include_router(router)


@app.get("/api/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"ok": True, "ai_available": ai_available(), "db_ok": db_ok}
