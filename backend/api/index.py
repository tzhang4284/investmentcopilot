"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI `app` exported here; all routes are
rewritten to this function via vercel.json. Tables are created at import time
because the lifespan hook is not guaranteed to run in serverless.
"""
from app.db import init_db
from app.main import app  # noqa: F401

init_db()
