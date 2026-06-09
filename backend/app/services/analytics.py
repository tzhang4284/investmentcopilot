"""Portfolio risk/return analytics.

Without historical account snapshots, the portfolio return series is approximated
by holding the *current* weights over the lookback window ("current-holdings
backfill"). The methodology is labeled in every response so the UI can disclose it.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..config import settings
from . import market_data, portfolio

TRADING_DAYS = 252


def _weighted_returns(db: Session, holdings: list[dict], period: str = "1y") -> Optional[pd.Series]:
    equity = [h for h in holdings if h["asset_class"] == "equity" and h["quantity"] > 0]
    if not equity:
        return None
    series: dict[str, pd.Series] = {}
    values: dict[str, float] = {}
    for h in equity:
        hist = market_data.get_history(db, h["ticker"], period)
        if not hist or not hist.get("points"):
            continue
        closes = pd.Series(
            [p["close"] for p in hist["points"]],
            index=pd.to_datetime([p["date"] for p in hist["points"]]),
        )
        series[h["ticker"]] = closes
        price = float(closes.iloc[-1])
        values[h["ticker"]] = h["quantity"] * price
    if not series:
        return None
    df = pd.DataFrame(series).dropna()
    if len(df) < 20:
        return None
    total = sum(values.values())
    weights = {tk: v / total for tk, v in values.items()}
    rets = df.pct_change().dropna()
    return (rets * pd.Series(weights)).sum(axis=1)


def compute_metrics(db: Session, period: str = "1y") -> dict:
    holdings = portfolio.get_holdings(db)
    if not holdings:
        return {"error": "No holdings. Upload a positions CSV first."}
    port_rets = _weighted_returns(db, holdings, period)
    if port_rets is None or port_rets.empty:
        return {
            "error": "Insufficient price history to compute metrics.",
            "method": "current-holdings-backfill",
        }

    ann_return = float((1 + port_rets.mean()) ** TRADING_DAYS - 1)
    vol = float(port_rets.std() * math.sqrt(TRADING_DAYS))
    rf = settings.risk_free_rate
    sharpe = (ann_return - rf) / vol if vol > 0 else None

    beta = None
    spy_hist = market_data.get_history(db, "SPY", period)
    if spy_hist and spy_hist.get("points"):
        spy = pd.Series(
            [p["close"] for p in spy_hist["points"]],
            index=pd.to_datetime([p["date"] for p in spy_hist["points"]]),
        ).pct_change().dropna()
        joined = pd.concat([port_rets, spy], axis=1, join="inner").dropna()
        if len(joined) > 20 and joined.iloc[:, 1].var() > 0:
            beta = float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / joined.iloc[:, 1].var())

    cumulative = (1 + port_rets).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    max_dd = float(drawdown.min())

    return {
        "period": period,
        "annualized_return": round(ann_return, 4),
        "annualized_volatility": round(vol, 4),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "beta_vs_spy": round(beta, 3) if beta is not None else None,
        "max_drawdown": round(max_dd, 4),
        "risk_free_rate": rf,
        "method": "current-holdings-backfill",
    }


def series_metrics(returns: pd.Series, rf: float = 0.045) -> dict:
    """Pure-function metrics on a daily-returns series (used by tests)."""
    ann_return = float((1 + returns.mean()) ** TRADING_DAYS - 1)
    vol = float(returns.std() * math.sqrt(TRADING_DAYS))
    cumulative = (1 + returns).cumprod()
    drawdown = cumulative / cumulative.cummax() - 1
    return {
        "annualized_return": ann_return,
        "annualized_volatility": vol,
        "sharpe": (ann_return - rf) / vol if vol > 0 else None,
        "max_drawdown": float(drawdown.min()),
    }


def beta(asset_returns: pd.Series, market_returns: pd.Series) -> Optional[float]:
    joined = pd.concat([asset_returns, market_returns], axis=1, join="inner").dropna()
    if len(joined) < 2 or joined.iloc[:, 1].var() == 0:
        return None
    return float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / joined.iloc[:, 1].var())


def compute_allocation(db: Session) -> dict:
    holdings = portfolio.get_holdings(db)
    if not holdings:
        return {"error": "No holdings. Upload a positions CSV first."}
    tickers = [h["ticker"] for h in holdings if h["asset_class"] == "equity"]
    quotes = market_data.get_quotes_bulk(db, tickers) if tickers else {}

    total = 0.0
    enriched = []
    for h in holdings:
        if h["asset_class"] == "cash":
            value = h["csv_value"] or h["quantity"]
            sector = "Cash"
        else:
            q = quotes.get(h["ticker"])
            price = q["price"] if q and q.get("price") else h.get("csv_price")
            value = h["quantity"] * price if price else (h["csv_value"] or 0.0)
            fund = market_data.get_fundamentals(db, h["ticker"])
            sector = (fund or {}).get("sector") or "Unknown"
        enriched.append({"ticker": h["ticker"], "value": value, "sector": sector, "asset_class": h["asset_class"]})
        total += value

    by_sector: dict[str, float] = {}
    by_class: dict[str, float] = {}
    for e in enriched:
        by_sector[e["sector"]] = by_sector.get(e["sector"], 0.0) + e["value"]
        by_class[e["asset_class"]] = by_class.get(e["asset_class"], 0.0) + e["value"]

    weights = sorted(
        ({"ticker": e["ticker"], "weight": e["value"] / total if total else 0} for e in enriched),
        key=lambda x: -x["weight"],
    )
    top5 = sum(w["weight"] for w in weights[:5])
    hhi = sum(w["weight"] ** 2 for w in weights)

    return {
        "total_value": round(total, 2),
        "by_sector": [
            {"sector": k, "value": round(v, 2), "weight": round(v / total, 4) if total else 0}
            for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])
        ],
        "by_asset_class": [
            {"asset_class": k, "value": round(v, 2), "weight": round(v / total, 4) if total else 0}
            for k, v in sorted(by_class.items(), key=lambda kv: -kv[1])
        ],
        "concentration": {"top5_weight": round(top5, 4), "hhi": round(hhi, 4)},
    }
