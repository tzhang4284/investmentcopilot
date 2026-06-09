"""AI thesis drafting and critique via structured outputs (messages.parse)."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import comps as comps_svc
from .. import insiders as insiders_svc
from .. import market_data
from .client import MODEL_DEEP, get_client


class ThesisDraft(BaseModel):
    thesis_text: str = Field(description="3-6 paragraph investment thesis: variant view, why now, what's priced in")
    target_price: float = Field(description="12-month price target in USD")
    time_horizon_months: int = Field(description="Time horizon in months")
    catalysts: list[str] = Field(description="3-5 specific upcoming catalysts")
    risks: list[str] = Field(description="3-5 key risks that would break the thesis")
    conviction: int = Field(description="Conviction 1-10 given the current evidence", ge=1, le=10)


class ThesisCritique(BaseModel):
    bull_case: str = Field(description="Strongest 2-3 paragraph bull argument")
    bear_case: str = Field(description="Strongest 2-3 paragraph bear argument")
    weakest_assumptions: list[str] = Field(description="The thesis's 2-4 weakest assumptions")
    what_would_change_my_mind: list[str] = Field(description="2-4 observable signposts that should trigger a re-underwrite")
    verdict: str = Field(description="One-paragraph net judgment: keep, trim, add, or exit, and why")


def _context_bundle(db: Session, ticker: str) -> str:
    """Assemble fundamentals + comps + insider summary as JSON context."""
    bundle = {
        "quote": market_data.get_quote(db, ticker),
        "fundamentals": market_data.get_fundamentals(db, ticker),
        "comps": comps_svc.build_comps(db, ticker),
        "insiders": insiders_svc.get_activity(db, ticker),
    }
    return json.dumps(bundle, default=str)


def draft_thesis(db: Session, ticker: str, direction: str, notes: str = "") -> ThesisDraft:
    ticker = ticker.upper()
    context = _context_bundle(db, ticker)
    prompt = (
        f"Draft an investment thesis for a {direction.upper()} position in {ticker}.\n\n"
        f"PM's initial notes (may be empty):\n{notes or '(none)'}\n\n"
        f"Market data context (JSON):\n{context}\n\n"
        "Ground the thesis in the data above. Be specific about valuation vs peers, "
        "and make the target price internally consistent with the multiples you cite."
    )
    response = get_client().messages.parse(
        model=MODEL_DEEP,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=ThesisDraft,
    )
    return response.parsed_output


def critique_thesis(db: Session, ticker: str, direction: str, thesis_text: str,
                    target_price: float | None, catalysts: list, risks: list) -> ThesisCritique:
    ticker = ticker.upper()
    context = _context_bundle(db, ticker)
    prompt = (
        f"Critique this {direction.upper()} thesis on {ticker} like a skeptical investment-committee member.\n\n"
        f"Thesis:\n{thesis_text}\n\nTarget price: {target_price}\n"
        f"Catalysts: {json.dumps(catalysts)}\nRisks: {json.dumps(risks)}\n\n"
        f"Current market data context (JSON):\n{context}\n\n"
        "Steelman both sides. Use current data to check whether the thesis assumptions still hold."
    )
    response = get_client().messages.parse(
        model=MODEL_DEEP,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
        output_format=ThesisCritique,
    )
    return response.parsed_output
