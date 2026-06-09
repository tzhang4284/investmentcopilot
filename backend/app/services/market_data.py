"""yfinance wrapper with a SQLite-backed TTL cache.

Yahoo endpoints are slow, rate-limited, and shape-shifting; every public function
here serves from cache when fresh, fetches on miss, and falls back to stale cache
(flagged "stale": true) when a fetch fails. Nothing raises to callers.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from ..models import MarketCache

logger = logging.getLogger(__name__)

TTL_QUOTE = 5 * 60
TTL_FUNDAMENTALS = 24 * 3600
TTL_HISTORY = 12 * 3600
TTL_PEERS = 7 * 24 * 3600

# Static peer map for common names; fallback when nothing better is available.
PEER_MAP: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL", "CRM"],
    "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
    "AMZN": ["GOOGL", "MSFT", "WMT", "BABA"],
    "META": ["GOOGL", "SNAP", "PINS", "MSFT"],
    "NVDA": ["AMD", "INTC", "AVGO", "QCOM", "TSM"],
    "AMD": ["NVDA", "INTC", "QCOM", "AVGO"],
    "TSLA": ["GM", "F", "RIVN", "LCID"],
    "JPM": ["BAC", "WFC", "C", "GS", "MS"],
    "BAC": ["JPM", "WFC", "C", "USB"],
    "XOM": ["CVX", "COP", "SHEL", "BP"],
    "CVX": ["XOM", "COP", "SHEL", "BP"],
    "UNH": ["ELV", "CI", "HUM", "CVS"],
    "JNJ": ["PFE", "MRK", "ABBV", "BMY", "LLY"],
    "PFE": ["MRK", "BMY", "JNJ", "ABBV"],
    "WMT": ["TGT", "COST", "KR", "AMZN"],
    "KO": ["PEP", "KDP", "MNST"],
    "DIS": ["NFLX", "CMCSA", "WBD", "PARA"],
    "NFLX": ["DIS", "WBD", "PARA", "ROKU"],
    "V": ["MA", "AXP", "PYPL"],
    "BRK/B": ["JPM", "BAC", "BLK"],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(db: Session, key: str) -> tuple[Optional[Any], Optional[float]]:
    """Return (payload, age_seconds) or (None, None)."""
    row = db.get(MarketCache, key)
    if row is None:
        return None, None
    fetched = row.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age = (_now() - fetched).total_seconds()
    try:
        return json.loads(row.payload), age
    except json.JSONDecodeError:
        return None, None


def _cache_put(db: Session, key: str, payload: Any) -> None:
    row = db.get(MarketCache, key)
    text = json.dumps(payload)
    if row is None:
        db.add(MarketCache(key=key, payload=text, fetched_at=_now()))
    else:
        row.payload = text
        row.fetched_at = _now()
    db.commit()


def cached(db: Session, key: str, ttl: int, fetch: Callable[[], Any]) -> Any:
    payload, age = _cache_get(db, key)
    if payload is not None and age is not None and age < ttl:
        return payload
    try:
        fresh = fetch()
    except Exception as exc:  # yfinance raises all sorts of things
        logger.warning("fetch failed for %s: %s", key, exc)
        fresh = None
    if fresh is not None:
        _cache_put(db, key, fresh)
        return fresh
    if payload is not None:
        if isinstance(payload, dict):
            payload["stale"] = True
        return payload
    return None


def _yf_symbol(ticker: str) -> str:
    return ticker.replace("/", "-").replace(".", "-")  # BRK/B -> BRK-B


def _safe(d: dict, *keys: str) -> Optional[Any]:
    for k in keys:
        v = d.get(k)
        if v is not None and v == v:  # filter NaN
            return v
    return None


def get_quote(db: Session, ticker: str) -> Optional[dict]:
    def fetch():
        import yfinance as yf

        t = yf.Ticker(_yf_symbol(ticker))
        info = {}
        try:
            fi = t.fast_info
            info = {
                "price": float(fi["last_price"]),
                "prev_close": float(fi["previous_close"]),
                "currency": fi.get("currency", "USD"),
            }
        except Exception:
            data = t.info or {}
            price = _safe(data, "currentPrice", "regularMarketPrice")
            if price is None:
                return None
            info = {
                "price": float(price),
                "prev_close": _safe(data, "previousClose", "regularMarketPreviousClose"),
                "currency": data.get("currency", "USD"),
            }
        if info.get("price") and info.get("prev_close"):
            info["change"] = info["price"] - info["prev_close"]
            info["change_pct"] = info["change"] / info["prev_close"] * 100
        info["ticker"] = ticker
        return info

    return cached(db, f"quote:{ticker}", TTL_QUOTE, fetch)


def get_quotes_bulk(db: Session, tickers: list[str]) -> dict[str, Optional[dict]]:
    """Quotes for many tickers. Serves cached-fresh; one bulk download for the rest."""
    out: dict[str, Optional[dict]] = {}
    missing: list[str] = []
    for tk in tickers:
        payload, age = _cache_get(db, f"quote:{tk}")
        if payload is not None and age is not None and age < TTL_QUOTE:
            out[tk] = payload
        else:
            missing.append(tk)
    if missing:
        try:
            import yfinance as yf

            symbols = {tk: _yf_symbol(tk) for tk in missing}
            data = yf.download(
                list(symbols.values()), period="5d", interval="1d",
                progress=False, group_by="ticker", auto_adjust=True,
            )
            for tk, sym in symbols.items():
                try:
                    closes = (data[sym]["Close"] if len(missing) > 1 else data["Close"]).dropna()
                    if len(closes) == 0:
                        out[tk] = get_quote(db, tk)
                        continue
                    price = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2]) if len(closes) > 1 else price
                    q = {
                        "ticker": tk,
                        "price": price,
                        "prev_close": prev,
                        "change": price - prev,
                        "change_pct": (price - prev) / prev * 100 if prev else 0.0,
                        "currency": "USD",
                    }
                    _cache_put(db, f"quote:{tk}", q)
                    out[tk] = q
                except Exception:
                    out[tk] = get_quote(db, tk)
        except Exception as exc:
            logger.warning("bulk quote download failed: %s", exc)
            for tk in missing:
                payload, _ = _cache_get(db, f"quote:{tk}")
                out[tk] = payload
    return out


def get_fundamentals(db: Session, ticker: str) -> Optional[dict]:
    def fetch():
        import yfinance as yf

        t = yf.Ticker(_yf_symbol(ticker))
        info = t.info or {}
        if not info or info.get("quoteType") is None and "longName" not in info:
            return None
        fcf = None
        try:
            cf = t.cashflow
            if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
                fcf = float(cf.loc["Free Cash Flow"].dropna().iloc[0])
        except Exception:
            pass
        revenue = _safe(info, "totalRevenue")
        return {
            "ticker": ticker,
            "name": _safe(info, "longName", "shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": _safe(info, "marketCap"),
            "enterprise_value": _safe(info, "enterpriseValue"),
            "pe_ttm": _safe(info, "trailingPE"),
            "pe_fwd": _safe(info, "forwardPE"),
            "ps": _safe(info, "priceToSalesTrailing12Months"),
            "ev_revenue": _safe(info, "enterpriseToRevenue"),
            "ev_ebitda": _safe(info, "enterpriseToEbitda"),
            "peg": _safe(info, "pegRatio", "trailingPegRatio"),
            "revenue": revenue,
            "revenue_growth": _safe(info, "revenueGrowth"),
            "gross_margin": _safe(info, "grossMargins"),
            "op_margin": _safe(info, "operatingMargins"),
            "net_margin": _safe(info, "profitMargins"),
            "fcf": fcf,
            "fcf_margin": (fcf / revenue) if (fcf and revenue) else None,
            "total_debt": _safe(info, "totalDebt"),
            "total_cash": _safe(info, "totalCash"),
            "dividend_yield": _safe(info, "dividendYield"),
            "beta": _safe(info, "beta"),
            "52w_high": _safe(info, "fiftyTwoWeekHigh"),
            "52w_low": _safe(info, "fiftyTwoWeekLow"),
            "summary": (info.get("longBusinessSummary") or "")[:1200] or None,
        }

    return cached(db, f"fundamentals:{ticker}", TTL_FUNDAMENTALS, fetch)


def get_history(db: Session, ticker: str, period: str = "1y") -> Optional[dict]:
    if period not in ("1mo", "3mo", "6mo", "1y", "2y", "5y", "max"):
        period = "1y"

    def fetch():
        import yfinance as yf

        t = yf.Ticker(_yf_symbol(ticker))
        hist = t.history(period=period, interval="1d", auto_adjust=True)
        if hist is None or hist.empty:
            return None
        return {
            "ticker": ticker,
            "period": period,
            "points": [
                {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 4)}
                for idx, row in hist.iterrows()
            ],
        }

    return cached(db, f"history:{ticker}:{period}", TTL_HISTORY, fetch)


def suggest_peers(db: Session, ticker: str) -> list[str]:
    tk = ticker.upper()
    if tk in PEER_MAP:
        return PEER_MAP[tk]

    def fetch():
        # Best-effort: same-sector names we already know about via the static map.
        fund = get_fundamentals(db, tk)
        if not fund or not fund.get("sector"):
            return []
        sector = fund["sector"]
        peers = []
        for cand in PEER_MAP:
            cf = get_fundamentals(db, cand)
            if cf and cf.get("sector") == sector and cand != tk:
                peers.append(cand)
            if len(peers) >= 5:
                break
        return peers

    result = cached(db, f"peers:{tk}", TTL_PEERS, fetch)
    return result if isinstance(result, list) else []
