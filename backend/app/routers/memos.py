from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Memo
from ..schemas import MemoGenerateRequest, MemoOut
from ..services.ai.client import ai_available

router = APIRouter(prefix="/api/memos", tags=["memos"])


@router.get("", response_model=list[MemoOut])
def list_memos(db: Session = Depends(get_db)):
    return db.execute(select(Memo).order_by(Memo.created_at.desc())).scalars().all()


@router.get("/{memo_id}", response_model=MemoOut)
def get_memo(memo_id: int, db: Session = Depends(get_db)):
    memo = db.get(Memo, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    return memo


@router.delete("/{memo_id}")
def delete_memo(memo_id: int, db: Session = Depends(get_db)):
    memo = db.get(Memo, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    db.delete(memo)
    db.commit()
    return {"ok": True}


@router.post("/generate", response_model=MemoOut)
def generate(body: MemoGenerateRequest, db: Session = Depends(get_db)):
    if not ai_available():
        raise HTTPException(status_code=503, detail="AI unavailable: set ANTHROPIC_API_KEY")
    from ..services.ai.memo import generate_memo

    try:
        return generate_memo(db, body.ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Memo generation failed: {exc}")
