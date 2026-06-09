from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Thesis
from ..schemas import ThesisCreate, ThesisDraftRequest, ThesisOut, ThesisUpdate
from ..services import market_data
from ..services.ai.client import ai_available

router = APIRouter(prefix="/api/theses", tags=["theses"])


def _require_ai():
    if not ai_available():
        raise HTTPException(status_code=503, detail="AI unavailable: set ANTHROPIC_API_KEY")


@router.get("", response_model=list[ThesisOut])
def list_theses(db: Session = Depends(get_db)):
    return db.execute(select(Thesis).order_by(Thesis.updated_at.desc())).scalars().all()


@router.post("", response_model=ThesisOut)
def create_thesis(body: ThesisCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["ticker"] = body.ticker.upper()
    thesis = Thesis(**data)
    db.add(thesis)
    db.commit()
    db.refresh(thesis)
    return thesis


@router.get("/{thesis_id}", response_model=ThesisOut)
def get_thesis(thesis_id: int, db: Session = Depends(get_db)):
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return thesis


@router.put("/{thesis_id}", response_model=ThesisOut)
def update_thesis(thesis_id: int, body: ThesisUpdate, db: Session = Depends(get_db)):
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(thesis, key, value)
    db.commit()
    db.refresh(thesis)
    return thesis


@router.delete("/{thesis_id}")
def delete_thesis(thesis_id: int, db: Session = Depends(get_db)):
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    db.delete(thesis)
    db.commit()
    return {"ok": True}


@router.get("/{thesis_id}/performance")
def thesis_performance(thesis_id: int, db: Session = Depends(get_db)):
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    quote = market_data.get_quote(db, thesis.ticker)
    current = quote.get("price") if quote else None
    out = {
        "thesis_id": thesis.id,
        "ticker": thesis.ticker,
        "direction": thesis.direction,
        "entry_price": thesis.entry_price,
        "current_price": current,
        "target_price": thesis.target_price,
    }
    if current and thesis.entry_price:
        sign = 1 if thesis.direction == "long" else -1
        out["return_pct"] = sign * (current - thesis.entry_price) / thesis.entry_price * 100
    if current and thesis.target_price and thesis.entry_price and thesis.target_price != thesis.entry_price:
        out["progress_to_target"] = (current - thesis.entry_price) / (thesis.target_price - thesis.entry_price)
    return out


@router.post("/draft")
def draft(body: ThesisDraftRequest, db: Session = Depends(get_db)):
    _require_ai()
    from ..services.ai.thesis import draft_thesis

    try:
        result = draft_thesis(db, body.ticker, body.direction, body.notes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI draft failed: {exc}")
    return result.model_dump()


@router.post("/{thesis_id}/critique")
def critique(thesis_id: int, db: Session = Depends(get_db)):
    _require_ai()
    thesis = db.get(Thesis, thesis_id)
    if not thesis:
        raise HTTPException(status_code=404, detail="Thesis not found")
    from ..services.ai.thesis import critique_thesis

    try:
        result = critique_thesis(
            db, thesis.ticker, thesis.direction, thesis.thesis_text,
            thesis.target_price, thesis.catalysts, thesis.risks,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI critique failed: {exc}")
    return result.model_dump()
