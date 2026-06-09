"""Comparables analysis: comps table with peer medians and premium/discount."""

from __future__ import annotations

import statistics
from typing import Optional

from sqlalchemy.orm import Session

from . import market_data

METRICS = [
    ("market_cap", "Market Cap"),
    ("enterprise_value", "EV"),
    ("ev_revenue", "EV/Revenue"),
    ("ev_ebitda", "EV/EBITDA"),
    ("pe_ttm", "P/E (TTM)"),
    ("pe_fwd", "P/E (Fwd)"),
    ("ps", "P/S"),
    ("revenue_growth", "Rev Growth"),
    ("gross_margin", "Gross Margin"),
    ("op_margin", "Op Margin"),
    ("fcf_margin", "FCF Margin"),
]

MULTIPLES = ["ev_revenue", "ev_ebitda", "pe_ttm", "pe_fwd", "ps"]


def build_comps(db: Session, target: str, peers: Optional[list[str]] = None) -> dict:
    target = target.upper()
    if not peers:
        peers = market_data.suggest_peers(db, target)
    peers = [p.upper() for p in peers if p.upper() != target]

    rows = []
    for ticker in [target] + peers:
        fund = market_data.get_fundamentals(db, ticker)
        row = {"ticker": ticker, "is_target": ticker == target}
        if fund:
            row["name"] = fund.get("name")
            row["sector"] = fund.get("sector")
            for key, _ in METRICS:
                row[key] = fund.get(key)
        else:
            row["error"] = "no data"
        rows.append(row)

    peer_rows = [r for r in rows if not r["is_target"] and "error" not in r]
    stats: dict[str, dict] = {}
    for key, _ in METRICS:
        vals = [r[key] for r in peer_rows if isinstance(r.get(key), (int, float))]
        stats[key] = {
            "median": statistics.median(vals) if vals else None,
            "mean": statistics.fmean(vals) if vals else None,
        }

    target_row = rows[0]
    premium_discount = {}
    for key in MULTIPLES:
        tv = target_row.get(key)
        med = stats[key]["median"]
        if isinstance(tv, (int, float)) and isinstance(med, (int, float)) and med != 0:
            premium_discount[key] = round((tv - med) / med, 4)
        else:
            premium_discount[key] = None

    return {
        "target": target,
        "peers": peers,
        "metrics": [{"key": k, "label": label} for k, label in METRICS],
        "rows": rows,
        "peer_stats": stats,
        "target_premium_discount_vs_median": premium_discount,
    }
