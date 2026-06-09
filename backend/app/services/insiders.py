"""Insider activity: Form 4 ingestion, cluster-buy detection, sentiment scoring."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InsiderTransaction
from . import edgar


def refresh(db: Session, ticker: str, limit: int = 15) -> dict:
    rows = edgar.fetch_form4s(db, ticker, limit=limit)
    existing = set(
        db.execute(
            select(InsiderTransaction.accession_no, InsiderTransaction.row_index).where(
                InsiderTransaction.ticker == ticker.upper()
            )
        ).all()
    )
    inserted = 0
    for r in rows:
        key = (r["accession_no"], r["row_index"])
        if key in existing:
            continue
        txn_date = None
        if r.get("transaction_date"):
            try:
                txn_date = datetime.strptime(r["transaction_date"][:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        db.add(
            InsiderTransaction(
                ticker=ticker.upper(),
                cik=str(r.get("cik", "")),
                insider_name=r["insider_name"],
                insider_title=r["insider_title"],
                is_director=r["is_director"],
                is_officer=r["is_officer"],
                transaction_date=txn_date,
                transaction_code=r["transaction_code"],
                shares=r.get("shares"),
                price=r.get("price"),
                value=r.get("value"),
                accession_no=r["accession_no"],
                row_index=r["row_index"],
            )
        )
        inserted += 1
    db.commit()
    return {"ticker": ticker.upper(), "fetched_rows": len(rows), "inserted": inserted}


def get_activity(db: Session, ticker: str, days: int = 365) -> dict:
    cutoff = date.today() - timedelta(days=days)
    txns = (
        db.execute(
            select(InsiderTransaction)
            .where(
                InsiderTransaction.ticker == ticker.upper(),
                InsiderTransaction.transaction_date >= cutoff,
            )
            .order_by(InsiderTransaction.transaction_date.desc())
        )
        .scalars()
        .all()
    )
    items = [
        {
            "date": t.transaction_date.isoformat() if t.transaction_date else None,
            "insider_name": t.insider_name,
            "insider_title": t.insider_title or ("Director" if t.is_director else ""),
            "code": t.transaction_code,
            "shares": t.shares,
            "price": t.price,
            "value": t.value,
        }
        for t in txns
    ]
    return {
        "ticker": ticker.upper(),
        "transactions": items,
        "cluster_buys": detect_cluster_buys(txns),
        "sentiment": sentiment(txns),
    }


def detect_cluster_buys(txns: list[InsiderTransaction], window_days: int = 14, min_insiders: int = 3) -> list[dict]:
    """Windows where >= min_insiders distinct insiders made open-market buys (code P)."""
    buys = sorted(
        (t for t in txns if t.transaction_code == "P" and t.transaction_date),
        key=lambda t: t.transaction_date,
    )
    clusters = []
    i = 0
    while i < len(buys):
        window_end = buys[i].transaction_date + timedelta(days=window_days)
        in_window = [t for t in buys[i:] if t.transaction_date <= window_end]
        insiders = {t.insider_name for t in in_window}
        if len(insiders) >= min_insiders:
            clusters.append(
                {
                    "start": buys[i].transaction_date.isoformat(),
                    "end": max(t.transaction_date for t in in_window).isoformat(),
                    "insiders": sorted(insiders),
                    "total_value": sum(t.value or 0 for t in in_window),
                }
            )
            i += len(in_window)
        else:
            i += 1
    return clusters


def sentiment(txns: list[InsiderTransaction], days: int = 90) -> dict:
    """Net insider buy/sell value over the window → score in [-1, 1]."""
    cutoff = date.today() - timedelta(days=days)
    buy_value = sell_value = 0.0
    for t in txns:
        if not t.transaction_date or t.transaction_date < cutoff or not t.value:
            continue
        if t.transaction_code == "P":
            buy_value += t.value
        elif t.transaction_code == "S":
            sell_value += t.value
    total = buy_value + sell_value
    score = (buy_value - sell_value) / total if total > 0 else 0.0
    label = "Bullish" if score > 0.3 else "Bearish" if score < -0.3 else "Neutral"
    return {
        "score": round(score, 3),
        "label": label,
        "buy_value_90d": buy_value,
        "sell_value_90d": sell_value,
    }
