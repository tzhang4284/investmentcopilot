"""Fidelity CSV export parsers.

Positions export ("Portfolio_Positions_*.csv") header:
  Account Number,Account Name,Symbol,Description,Quantity,Last Price,...,
  Current Value,...,Cost Basis Total,Average Cost Basis,Type
Footer: blank lines, '"Date downloaded ..."', disclaimer paragraphs.

Transactions export ("History_for_Account_*.csv") header:
  Run Date,Account,Action,Symbol,Description,Type,Quantity,Price ($),
  Commission ($),Fees ($),Accrued Interest ($),Amount ($),Settlement Date
Actions: "YOU BOUGHT ...", "YOU SOLD ...", "DIVIDEND RECEIVED", "REINVESTMENT", etc.
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
    "Account Number",
    "Account Name",
    "Symbol",
    "Description",
    "Quantity",
    "Last Price",
    "Current Value",
    "Cost Basis Total",
    "Average Cost Basis",
    "Type",
]

TRANSACTION_COLUMNS = [
    "Run Date",
    "Account",
    "Action",
    "Symbol",
    "Description",
    "Quantity",
    "Price ($)",
    "Commission ($)",
    "Fees ($)",
    "Amount ($)",
    "Settlement Date",
]


def classify_action(action: str) -> str:
    a = action.upper()
    if "BOUGHT" in a or a.startswith("BUY"):
        return "buy"
    if "SOLD" in a or a.startswith("SELL"):
        return "sell"
    if "REINVESTMENT" in a or "REINVEST" in a:
        return "reinvest"
    if "DIVIDEND" in a:
        return "dividend"
    if "INTEREST" in a:
        return "interest"
    if "TRANSFER" in a or "RECEIVED" in a or "CONTRIBUTION" in a or "DEPOSIT" in a:
        return "transfer"
    return "other"


@register_adapter
class FidelityAdapter(BrokerAdapter):
    broker_name = "fidelity"

    @classmethod
    def sniff(cls, text: str) -> Optional[FileKind]:
        head = "\n".join(text.splitlines()[:40]).lower()
        if "cost basis total" in head and "symbol" in head:
            return FileKind.POSITIONS
        if "run date" in head and "settlement date" in head:
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
            is_cash = bool(MONEY_MARKET_PATTERNS.match(symbol)) or symbol.upper() in (
                "CASH",
                "PENDING ACTIVITY",
            )
            current_value = to_float(row.get("currentvalue"))
            if quantity is None:
                if is_cash and current_value is not None:
                    quantity = current_value  # cash: 1 share == $1
                else:
                    result.skipped_rows.append(raw)
                    continue
            result.positions.append(
                NormalizedPosition(
                    ticker=symbol.rstrip("*"),
                    quantity=quantity,
                    description=row.get("description", ""),
                    cost_basis=to_float(row.get("costbasistotal")),
                    last_price=to_float(row.get("lastprice")),
                    current_value=current_value,
                    asset_class="cash" if is_cash else "equity",
                    account_label=row.get("accountname") or row.get("accountnumber", ""),
                )
            )
        return result

    def parse_transactions(self, text: str) -> ParseResult:
        result = ParseResult()
        for row, raw in iter_data_rows(text, TRANSACTION_COLUMNS):
            if row is None:
                result.skipped_rows.append(raw)
                continue
            action_raw = (row.get("action") or "").strip()
            trade_date = to_date(row.get("rundate"))
            if not action_raw or trade_date is None:
                result.skipped_rows.append(raw)
                continue
            fees = (to_float(row.get("commission")) or 0.0) + (to_float(row.get("fees")) or 0.0)
            result.transactions.append(
                NormalizedTransaction(
                    action=classify_action(action_raw),
                    ticker=(row.get("symbol") or "").strip().rstrip("*"),
                    trade_date=trade_date,
                    settle_date=to_date(row.get("settlementdate")),
                    quantity=to_float(row.get("quantity")),
                    price=to_float(row.get("price")),
                    amount=to_float(row.get("amount")),
                    fees=fees or None,
                    raw_description=action_raw,
                    account_label=row.get("account", ""),
                )
            )
        return result
