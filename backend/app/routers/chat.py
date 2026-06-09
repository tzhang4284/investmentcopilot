from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import ChatRequest
from ..services.ai.client import ai_available

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    if not ai_available():
        raise HTTPException(status_code=503, detail="AI unavailable: set ANTHROPIC_API_KEY")
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages must be non-empty")

    from ..services.ai.chat import stream_chat

    return EventSourceResponse(
        stream_chat(db, body.messages),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
