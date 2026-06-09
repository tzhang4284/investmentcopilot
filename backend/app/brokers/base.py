"""Broker adapter interface + shared helpers for parsing messy brokerage CSV exports.

Real exports from Fidelity / Merrill Edge include preamble lines before the header,
disclaimer footers, currency symbols, thousands separators, "--" placeholders,
parenthesized negatives, and pseudo-rows (totals, pending activity, money-market cash).
The helpers here deal with all of that so the per-broker adapters stay declarative.

A future live connector (Plaid/SnapTrade) implements the same interface, returning
NormalizedPosition / NormalizedTransaction from API payloads instead of CSV text.
"""

from __future__ import annotations

import csv
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class FileKind(str, Enum):
    POSITIONS = "positions"
    TRANSACTIONS = "transactions"


@dataclass
class NormalizedPosition:
    ticker: str
    quantity: float
    description: str = ""
    cost_basis: Optional[float] = None  # total dollars
    last_price: Optional[float] = None
    current_value: Optional[float] = None
    asset_class: str = "equity"
    account_label: str = ""
    as_of_date: Optional[date] = None


@dataclass
class NormalizedTransaction:
    action: str  # buy|sell|dividend|interest|reinvest|transfer|other
    ticker: str = ""
    trade_date: Optional[date] = None
    settle_date: Optional[date] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    fees: Optional[float] = None
    raw_description: str = ""
    account_label: str = ""


@dataclass
class ParseResult:
    positions: list[NormalizedPosition] = field(default_factory=list)
    transactions: list[NormalizedTransaction] = field(default_factory=list)
    skipped_rows: list[str] = field(default_factory=list)


MONEY_MARKET_PATTERNS = re.compile(
    r"^(SPAXX|FDRXX|FZFXX|FCASH|CORE|QACDS|TLGXX|FDIC|MMDA)", re.IGNORECASE
)

FOOTER_KEYWORDS = (
    "total",
    "pending activity",
    "date downloaded",
    "the data and information",
    "brokerage services",
    "cash & money accounts",
    "balances",
)


def to_float(raw: str | None) -> Optional[float]:
    """Parse a brokerage-CSV numeric cell. Returns None for placeholders."""
    if raw is None:
        return None
    s = raw.strip().strip('"').replace("$", "").replace(",", "").replace("%", "").strip()
    if s in ("", "--", "-", "n/a", "N/A", "NA", "null"):
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        negative = True
    if s.endswith("-"):
        s = s[:-1]
        negative = True
    if s.startswith("+"):
        s = s[1:]
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if negative else val


def to_date(raw: str | None) -> Optional[date]:
    if not raw:
        return None
    s = raw.strip().strip('"')
    if not s or s.lower() in ("--", "n/a"):
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%b %d, %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_header_row(lines: list[str], expected_columns: list[str], scan: int = 40) -> int:
    """Return index of the line that best matches the expected column names.

    Brokerage exports often have preamble lines (account info, export date) before
    the real header. Score each early line by how many expected columns it contains.
    """
    expected = {normalize_header(c) for c in expected_columns}
    best_idx, best_score = -1, 0
    for i, line in enumerate(lines[:scan]):
        try:
            cells = next(csv.reader([line]))
        except (csv.Error, StopIteration):
            continue
        names = {normalize_header(c) for c in cells if c.strip()}
        score = len(expected & names)
        if score > best_score:
            best_idx, best_score = i, score
    # Require at least 3 matching columns to call it a header.
    return best_idx if best_score >= 3 else -1


def iter_data_rows(text: str, expected_columns: list[str]):
    """Yield (row_dict, raw_line) for each data row after the sniffed header.

    row_dict keys are normalized header names. Rows that look like footers,
    totals, or junk are yielded with row_dict=None so callers can record skips.
    """
    text = text.lstrip("﻿")
    lines = text.splitlines()
    header_idx = find_header_row(lines, expected_columns)
    if header_idx < 0:
        return
    header_cells = next(csv.reader([lines[header_idx]]))
    keys = [normalize_header(c) for c in header_cells]
    reader = csv.reader(io.StringIO("\n".join(lines[header_idx + 1 :])))
    for cells in reader:
        raw_line = ",".join(cells)
        if not any(c.strip() for c in cells):
            continue
        first = (cells[0] or "").strip().lower()
        if any(first.startswith(k) for k in FOOTER_KEYWORDS):
            yield None, raw_line
            continue
        # Disclaimer prose: a single long cell with no commas worth of data
        if len([c for c in cells if c.strip()]) == 1 and len(cells[0]) > 80:
            continue
        if len(cells) < max(3, len(keys) // 2):
            yield None, raw_line
            continue
        row = {keys[i]: cells[i].strip() for i in range(min(len(keys), len(cells)))}
        yield row, raw_line


class BrokerAdapter(ABC):
    broker_name: str = "base"

    @classmethod
    @abstractmethod
    def sniff(cls, text: str) -> Optional[FileKind]:
        """Return the FileKind if this adapter recognizes the CSV text, else None."""

    @abstractmethod
    def parse_positions(self, text: str) -> ParseResult: ...

    @abstractmethod
    def parse_transactions(self, text: str) -> ParseResult: ...

    def parse(self, text: str, kind: FileKind) -> ParseResult:
        if kind == FileKind.POSITIONS:
            return self.parse_positions(text)
        return self.parse_transactions(text)


_ADAPTERS: list[type[BrokerAdapter]] = []


def register_adapter(cls: type[BrokerAdapter]) -> type[BrokerAdapter]:
    _ADAPTERS.append(cls)
    return cls


def detect_broker(text: str) -> tuple[Optional[BrokerAdapter], Optional[FileKind]]:
    text = text.lstrip("﻿")
    for cls in _ADAPTERS:
        kind = cls.sniff(text)
        if kind is not None:
            return cls(), kind
    return None, None
