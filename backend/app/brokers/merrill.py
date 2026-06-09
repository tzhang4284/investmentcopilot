"""Merrill Edge CSV export parsers.

Positions export header (after preamble like 'Positions as of ...'):
  Symbol,Description,Quantity,Price,Price Change,Value,Day Change,
  Unrealized Gain/Loss ($),Unrealized Gain/Loss (%),Cost Basis,Acquisition Date/Avg Cost
Footer rows: "Cash & Money Accounts", "Total", "Pending Activity".

Transactions export header:
  Trade Date,Settlement Date,Account,Description 1,Description 2,
  Symbol/CUSIP,Type,Quantity,Price,Amount
Types: Purchase, Sale, Dividend, Reinvestment, etc. Values often quoted "1,234.56".
"""

from __future__ import annotations

from typing import Optional

from .base import (
    MONEY_MARKET_PATTERNS,
    BrokerAdapter,
    FileKind,
    NormalizedPosition,
    NormalizedTransaction,
    ParseResult,
    iter_data_rows,
    register_adapter,
    to_date,
    to_float,
)

POSITION_COLUMNS = [
    "Symbol",
    "Description",
    "Quantity",
    "Price",
    "Value",
    "Unrealized Gain/Loss ($)",
    "Unrealized Gain/Loss (%)",
    "Cost Basis",
]

TRANSACTION_COLUMNS = [
    "Trade Date",
    "Settlement Date",
    "Account",
    "Description 1",
    "Symbol/CUSIP",
    "Type",
    "Quantity",
    "Price",
    "Amount",
]


def classify_type(t: str) -> str:
    t = t.lower()
    if "purchase" in t or t.startswith("buy"):
        return "buy"
    if "sale" in t or t.startswith("sell"):
        return "sell"
    if "reinvest" in t:
        return "reinvest"
    if "dividend" in t:
        return "dividend"
    if "interest" in t:
        return "interest"
    if "transfer" in t or "deposit" in t or "ach" in t:
        return "transfer"
    return "other"


@register_adapter
class MerrillAdapter(BrokerAdapter):
    broker_name = "merrill"

    @classmethod
    def sniff(cls, text: str) -> Optional[FileKind]:
        head = "\n".join(text.splitlines()[:40]).lower()
        if "unrealized gain/loss" in head:
            return FileKind.POSITIONS
        if "symbol/cusip" in head:
            return FileKind.TRANSACTIONS
        return None

    def parse_positions(self, text: str) -> ParseResult:
        result = ParseResult()
        for row, raw in iter_data_rows(text, POSITION_COLUMNS):
            if row is None:
                result.skipped_rows.append(raw)
                continue
            symbol = (row.get("symbol") or "").strip()
            if not symbol:
                result.skipped_rows.append(raw)
                continue
            quantity = to_float(row.get("quantity"))
            is_cash = bool(MONEY_MARKET_PATTERNS.match(symbol)) or "money" in (
                row.get("description") or ""
            ).lower()
            value = to_float(row.get("value"))
            if quantity is None:
                if is_cash and value is not None:
                    quantity = value
                else:
                    result.skipped_rows.append(raw)
                    continue
            result.positions.append(
                NormalizedPosition(
                    ticker=symbol.rstrip("*"),
                    quantity=quantity,
                    description=row.get("description", ""),
                    cost_basis=to_float(row.get("costbasis")),
                    last_price=to_float(row.get("price")),
                    current_value=value,
                    asset_class="cash" if is_cash else "equity",
                )
            )
        return result

    def parse_transactions(self, text: str) -> ParseResult:
        result = ParseResult()
        for row, raw in iter_data_rows(text, TRANSACTION_COLUMNS):
            if row is None:
                result.skipped_rows.append(raw)
                continue
            type_raw = (row.get("type") or "").strip()
            trade_date = to_date(row.get("tradedate"))
            if not type_raw or trade_date is None:
                result.skipped_rows.append(raw)
                continue
            symbol = (row.get("symbolcusip") or "").strip()
            # CUSIPs are 9 alphanumeric chars; keep ticker-looking symbols only
            if len(symbol) == 9 and any(c.isdigit() for c in symbol):
                symbol = ""
            desc = " ".join(
                p for p in (row.get("description1", ""), row.get("description2", "")) if p
            )
            result.transactions.append(
                NormalizedTransaction(
                    action=classify_type(type_raw),
                    ticker=symbol,
                    trade_date=trade_date,
                    settle_date=to_date(row.get("settlementdate")),
                    quantity=to_float(row.get("quantity")),
                    price=to_float(row.get("price")),
                    amount=to_float(row.get("amount")),
                    raw_description=f"{type_raw} {desc}".strip(),
                    account_label=row.get("account", ""),
                )
            )
        return result
