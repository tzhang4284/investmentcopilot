from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import insiders as insiders_svc

router = APIRouter(prefix="/api/insiders", tags=["insiders"])


@router.post("/{ticker}/refresh")
def refresh(ticker: str, db: Session = Depends(get_db)):
    return insiders_svc.refresh(db, ticker.upper())


@router.get("/{ticker}")
def activity(ticker: str, days: int = 365, db: Session = Depends(get_db)):
    return insiders_svc.get_activity(db, ticker.upper(), days)
