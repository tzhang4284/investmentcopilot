from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Transaction
from ..services import analytics, market_data
from ..services import portfolio as portfolio_svc

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    summary = portfolio_svc.ingest_csv(db, text)
    if not summary.get("ok"):
        raise HTTPException(status_code=400, detail=summary.get("error"))
    summary["filename"] = file.filename
    return summary


@router.get("/holdings")
def holdings(db: Session = Depends(get_db)):
    rows = portfolio_svc.get_holdings(db)
    tickers = [h["ticker"] for h in rows if h["asset_class"] == "equity"]
    quotes = market_data.get_quotes_bulk(db, tickers) if tickers else {}
    total = 0.0
    for h in rows:
        q = quotes.get(h["ticker"])
        price = q["price"] if q and q.get("price") else h.get("csv_price")
        if h["asset_class"] == "cash":
            h["market_value"] = h["csv_value"] or h["quantity"]
            h["price"] = 1.0
        else:
            h["price"] = price
            h["market_value"] = h["quantity"] * price if price else h["csv_value"]
            h["day_change_pct"] = q.get("change_pct") if q else None
        cost = h.get("cost_basis") or 0.0
        if h["market_value"] is not None and cost:
            h["unrealized_pnl"] = h["market_value"] - cost
            h["unrealized_pnl_pct"] = (h["market_value"] - cost) / cost * 100
        total += h["market_value"] or 0.0
    for h in rows:
        h["weight"] = (h["market_value"] or 0.0) / total if total else 0.0
    rows.sort(key=lambda h: -(h["market_value"] or 0.0))
    return {"total_value": round(total, 2), "holdings": rows}


@router.get("/transactions")
def transactions(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Transaction.id))).scalar()
    rows = db.execute(
        select(Transaction, Account)
        .join(Account, Transaction.account_id == Account.id)
        .order_by(Transaction.trade_date.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "total": total,
        "transactions": [
            {
                "id": t.id,
                "broker": a.broker,
                "trade_date": t.trade_date.isoformat() if t.trade_date else None,
                "ticker": t.ticker,
                "action": t.action,
                "quantity": t.quantity,
                "price": t.price,
                "amount": t.amount,
                "fees": t.fees,
                "description": t.raw_description,
            }
            for t, a in rows
        ],
    }


@router.get("/allocation")
def allocation(db: Session = Depends(get_db)):
    return analytics.compute_allocation(db)


@router.get("/metrics")
def metrics(period: str = "1y", db: Session = Depends(get_db)):
    return analytics.compute_metrics(db, period)
