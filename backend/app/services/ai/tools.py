"""Tool definitions + dispatcher for the AI analyst chat.

Each tool maps to an existing service function. The dispatcher returns JSON
strings; failures come back as error strings so the model can adapt.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Thesis
from .. import analytics, comps, edgar, insiders, market_data, portfolio

TOOLS = [
    {
        "name": "get_portfolio",
        "description": "Get the PM's current portfolio: holdings with quantities, cost basis, allocation by sector/asset class, concentration, and risk metrics (Sharpe, beta, drawdown). Call this whenever the user asks about 'my portfolio', 'my holdings', 'my exposure', or position sizing.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_quote",
        "description": "Get the latest price quote for a ticker. Call when the user asks about a current price or recent move.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_fundamentals",
        "description": "Get fundamentals for a ticker: valuation multiples (P/E, EV/EBITDA, P/S), growth, margins, FCF, debt, sector. Call before making any valuation or quality judgment about a company.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_comps",
        "description": "Build a comparables table for a target ticker vs peers: multiples, growth, margins, peer median/mean, and the target's premium/discount vs median. Call for any relative-valuation question. Peers optional — auto-suggested if omitted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "peers": {"type": "array", "items": {"type": "string"}, "description": "Optional peer tickers"},
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_insider_activity",
        "description": "Get recent SEC Form 4 insider transactions for a ticker, including cluster-buy detection and an insider sentiment score. Call when the user asks about insider buying/selling or management conviction. Data must have been refreshed at least once for the ticker; if empty, say so and suggest refreshing on the Insiders page.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_filings",
        "description": "List recent SEC filings (10-K, 10-Q, 8-K) for a ticker and optionally fetch the text of the most recent one of a given form type. Call when the user asks what a company said in its filings or about recent disclosures.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "form_type": {"type": "string", "description": "e.g. 10-K, 10-Q, 8-K. If provided, the text of the latest such filing is fetched (truncated)."},
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_theses",
        "description": "Get the PM's saved investment theses (direction, target price, catalysts, risks, status). Optionally filter by ticker. Call when the user references 'my thesis' or asks how a position is tracking vs plan.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Optional ticker filter"}},
            "additionalProperties": False,
        },
    },
]


def _portfolio_payload(db: Session) -> dict:
    return {
        "holdings": portfolio.get_holdings(db),
        "allocation": analytics.compute_allocation(db),
        "metrics": analytics.compute_metrics(db),
    }


def _theses_payload(db: Session, ticker: str | None) -> list[dict]:
    q = select(Thesis)
    if ticker:
        q = q.where(Thesis.ticker == ticker.upper())
    return [
        {
            "id": t.id,
            "ticker": t.ticker,
            "direction": t.direction,
            "target_price": t.target_price,
            "time_horizon_months": t.time_horizon_months,
            "thesis_text": t.thesis_text,
            "catalysts": t.catalysts,
            "risks": t.risks,
            "conviction": t.conviction,
            "status": t.status,
            "entry_price": t.entry_price,
        }
        for t in db.execute(q).scalars()
    ]


def _search_filings(db: Session, ticker: str, form_type: str | None) -> dict:
    forms = [form_type] if form_type else ["10-K", "10-Q", "8-K"]
    filings = edgar.recent_filings(db, ticker, form_types=forms, limit=10)
    out: dict = {"ticker": ticker.upper(), "filings": filings}
    if form_type and filings:
        f = filings[0]
        text = edgar.fetch_filing_text(db, f["cik"], f["accession_no"], f["primary_doc"], max_chars=30_000)
        out["latest_filing_text"] = text or "(fetch failed)"
    return out


def dispatch(db: Session, name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool. Returns (result_json, is_error)."""
    try:
        if name == "get_portfolio":
            result = _portfolio_payload(db)
        elif name == "get_quote":
            result = market_data.get_quote(db, tool_input["ticker"].upper()) or {"error": "no quote available"}
        elif name == "get_fundamentals":
            result = market_data.get_fundamentals(db, tool_input["ticker"].upper()) or {"error": "no fundamentals available"}
        elif name == "get_comps":
            result = comps.build_comps(db, tool_input["ticker"], tool_input.get("peers"))
        elif name == "get_insider_activity":
            result = insiders.get_activity(db, tool_input["ticker"])
        elif name == "search_filings":
            result = _search_filings(db, tool_input["ticker"], tool_input.get("form_type"))
        elif name == "get_theses":
            result = _theses_payload(db, tool_input.get("ticker"))
        else:
            return f"Unknown tool: {name}", True
        return json.dumps(result, default=str), False
    except Exception as exc:
        return f"Tool {name} failed: {exc}", True
