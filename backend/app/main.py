from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

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
