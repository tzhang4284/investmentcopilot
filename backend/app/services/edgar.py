"""SEC EDGAR client: CIK lookup, filings, Form 4 parsing, company facts.

SEC etiquette: a descriptive User-Agent with contact info is required (403 without),
and requests must stay well under 10/s — we throttle to ~6/s.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Optional

import httpx
from lxml import etree
from sqlalchemy.orm import Session

from ..config import settings
from .market_data import cached

logger = logging.getLogger(__name__)

_MIN_INTERVAL = 0.15
_last_request = 0.0
_lock = threading.Lock()

TTL_CIK_MAP = 7 * 24 * 3600
TTL_SUBMISSIONS = 6 * 3600
TTL_FACTS = 24 * 3600


def _get(url: str, timeout: float = 20.0) -> httpx.Response:
    global _last_request
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
    resp = httpx.get(
        url,
        headers={"User-Agent": settings.edgar_user_agent, "Accept-Encoding": "gzip"},
        timeout=timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp


def ticker_to_cik(db: Session, ticker: str) -> Optional[str]:
    def fetch():
        data = _get("https://www.sec.gov/files/company_tickers.json").json()
        return {v["ticker"].upper(): str(v["cik_str"]) for v in data.values()}

    mapping = cached(db, "edgar:cik_map", TTL_CIK_MAP, fetch)
    if not mapping:
        return None
    return mapping.get(ticker.upper().replace("/", "-").replace(".", "-")) or mapping.get(
        ticker.upper()
    )


def get_submissions(db: Session, cik: str) -> Optional[dict]:
    def fetch():
        return _get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()

    return cached(db, f"edgar:submissions:{cik}", TTL_SUBMISSIONS, fetch)


def recent_filings(db: Session, ticker: str, form_types: list[str] | None = None, limit: int = 20) -> list[dict]:
    cik = ticker_to_cik(db, ticker)
    if not cik:
        return []
    subs = get_submissions(db, cik)
    if not subs:
        return []
    recent = subs.get("filings", {}).get("recent", {})
    out = []
    forms = recent.get("form", [])
    for i in range(len(forms)):
        form = forms[i]
        if form_types and form not in form_types:
            continue
        out.append(
            {
                "form": form,
                "filing_date": recent["filingDate"][i],
                "accession_no": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
                "description": recent.get("primaryDocDescription", [""] * len(forms))[i],
                "cik": cik,
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_filing_text(db: Session, cik: str, accession_no: str, primary_doc: str, max_chars: int = 50_000) -> Optional[str]:
    acc = accession_no.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{primary_doc}"
    try:
        html = _get(url, timeout=30.0).text
    except Exception as exc:
        logger.warning("filing fetch failed %s: %s", url, exc)
        return None
    # Strip tags crudely; good enough for LLM context.
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _xpath_text(node, path: str) -> Optional[str]:
    found = node.find(path)
    if found is not None and found.text:
        return found.text.strip()
    return None


def parse_form4(xml_bytes: bytes) -> list[dict]:
    """Parse a Form 4 XML doc into normalized non-derivative transaction rows."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return []
    owner = root.find("reportingOwner")
    name = title = ""
    is_dir = is_off = False
    if owner is not None:
        name = _xpath_text(owner, ".//rptOwnerName") or ""
        rel = owner.find("reportingOwnerRelationship")
        if rel is not None:
            is_dir = (_xpath_text(rel, "isDirector") or "0") in ("1", "true")
            is_off = (_xpath_text(rel, "isOfficer") or "0") in ("1", "true")
            title = _xpath_text(rel, "officerTitle") or ""
    rows = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        code = _xpath_text(txn, ".//transactionCode")
        if not code:
            continue
        shares_s = _xpath_text(txn, ".//transactionShares/value")
        price_s = _xpath_text(txn, ".//transactionPricePerShare/value")
        date_s = _xpath_text(txn, ".//transactionDate/value")
        try:
            shares = float(shares_s) if shares_s else None
        except ValueError:
            shares = None
        try:
            price = float(price_s) if price_s else None
        except ValueError:
            price = None
        rows.append(
            {
                "insider_name": name,
                "insider_title": title,
                "is_director": is_dir,
                "is_officer": is_off,
                "transaction_date": date_s,
                "transaction_code": code,
                "shares": shares,
                "price": price,
                "value": (shares * price) if (shares and price) else None,
            }
        )
    return rows


def fetch_form4s(db: Session, ticker: str, limit: int = 15) -> list[dict]:
    """Fetch recent Form 4 filings for a ticker; returns parsed rows with accession ids."""
    filings = recent_filings(db, ticker, form_types=["4"], limit=limit)
    all_rows: list[dict] = []
    for f in filings:
        acc = f["accession_no"].replace("-", "")
        doc = f["primary_doc"]
        # Form 4 primary doc may be .../xslF345X05/foo.xml — strip the XSL prefix for raw XML.
        doc = doc.split("/")[-1]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(f['cik'])}/{acc}/{doc}"
        try:
            xml = _get(url, timeout=20.0).content
        except Exception as exc:
            logger.warning("form4 fetch failed %s: %s", url, exc)
            continue
        rows = parse_form4(xml)
        for i, row in enumerate(rows):
            row["accession_no"] = f["accession_no"]
            row["row_index"] = i
            row["cik"] = f["cik"]
        all_rows.extend(rows)
    return all_rows


def get_company_facts(db: Session, ticker: str) -> Optional[dict]:
    cik = ticker_to_cik(db, ticker)
    if not cik:
        return None

    def fetch():
        data = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json").json()
        out: dict[str, Any] = {"ticker": ticker, "entity": data.get("entityName")}
        gaap = data.get("facts", {}).get("us-gaap", {})

        def annual_series(*tags: str) -> list[dict]:
            for tag in tags:
                units = gaap.get(tag, {}).get("units", {})
                vals = units.get("USD") or units.get("USD/shares") or []
                annual = [
                    v for v in vals
                    if v.get("form") == "10-K" and v.get("fp") == "FY" and v.get("frame") is None
                ]
                seen: dict[str, dict] = {}
                for v in annual:
                    fy = str(v.get("fy"))
                    seen[fy] = v  # keep latest restatement
                series = sorted(
                    ({"fy": k, "value": v["val"], "end": v.get("end")} for k, v in seen.items()),
                    key=lambda x: x["fy"],
                )
                if series:
                    return series[-6:]
            return []

        out["revenue"] = annual_series("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
        out["net_income"] = annual_series("NetIncomeLoss")
        out["eps_diluted"] = annual_series("EarningsPerShareDiluted")
        return out

    return cached(db, f"edgar:facts:{ticker}", TTL_FACTS, fetch)
