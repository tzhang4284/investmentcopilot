from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import comps as comps_svc
from ..services import edgar, market_data

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/{ticker}/quote")
def quote(ticker: str, db: Session = Depends(get_db)):
    q = market_data.get_quote(db, ticker.upper())
    if q is None:
        raise HTTPException(status_code=404, detail=f"No quote available for {ticker}")
    return q


@router.get("/{ticker}/fundamentals")
def fundamentals(ticker: str, db: Session = Depends(get_db)):
    f = market_data.get_fundamentals(db, ticker.upper())
    if f is None:
        raise HTTPException(status_code=404, detail=f"No fundamentals available for {ticker}")
    return f


@router.get("/{ticker}/history")
def history(ticker: str, period: str = "1y", db: Session = Depends(get_db)):
    h = market_data.get_history(db, ticker.upper(), period)
    if h is None:
        raise HTTPException(status_code=404, detail=f"No history available for {ticker}")
    return h


@router.get("/{ticker}/financials")
def financials(ticker: str, db: Session = Depends(get_db)):
    facts = edgar.get_company_facts(db, ticker.upper())
    if facts is None:
        raise HTTPException(status_code=404, detail=f"No EDGAR facts for {ticker}")
    return facts


@router.get("/{ticker}/peers")
def peers(ticker: str, db: Session = Depends(get_db)):
    return {"ticker": ticker.upper(), "peers": market_data.suggest_peers(db, ticker.upper())}


@router.get("/{ticker}/comps")
def comps(ticker: str, peers: str = "", db: Session = Depends(get_db)):
    peer_list = [p.strip().upper() for p in peers.split(",") if p.strip()] or None
    return comps_svc.build_comps(db, ticker.upper(), peer_list)
