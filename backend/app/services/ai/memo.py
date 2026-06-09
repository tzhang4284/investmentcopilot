"""One-pager research memo generation."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Memo, Thesis
from .. import comps as comps_svc
from .. import insiders as insiders_svc
from .. import market_data
from .client import MODEL_DEEP, get_client

MEMO_PROMPT = """Write a one-page research memo on {ticker} in markdown.

Sections (use these exact headers):
## Snapshot
## Business
## Valuation vs Peers
## Insider Activity
## Catalysts
## Risks
## View

Data context (JSON):
{context}

Active thesis (may be null):
{thesis}

Rules: be specific and quantitative, cite numbers from the context, keep it to roughly
one page, write like a buy-side analyst memo for the PM. If a data section is empty,
say so in one line rather than inventing figures."""


def generate_memo(db: Session, ticker: str) -> Memo:
    ticker = ticker.upper()
    context = json.dumps(
        {
            "quote": market_data.get_quote(db, ticker),
            "fundamentals": market_data.get_fundamentals(db, ticker),
            "comps": comps_svc.build_comps(db, ticker),
            "insiders": insiders_svc.get_activity(db, ticker),
        },
        default=str,
    )
    thesis = db.execute(
        select(Thesis).where(Thesis.ticker == ticker, Thesis.status == "active")
    ).scalar_one_or_none()
    thesis_json = (
        json.dumps(
            {
                "direction": thesis.direction,
                "target_price": thesis.target_price,
                "thesis_text": thesis.thesis_text,
                "catalysts": thesis.catalysts,
                "risks": thesis.risks,
            }
        )
        if thesis
        else "null"
    )

    with get_client().messages.stream(
        model=MODEL_DEEP,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": MEMO_PROMPT.format(ticker=ticker, context=context, thesis=thesis_json),
            }
        ],
    ) as s:
        final = s.get_final_message()
    content = next((b.text for b in final.content if b.type == "text"), "")

    memo = Memo(ticker=ticker, title=f"{ticker} — Research Memo", content_md=content)
    db.add(memo)
    db.commit()
    db.refresh(memo)
    return memo
