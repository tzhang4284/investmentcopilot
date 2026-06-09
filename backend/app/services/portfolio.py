"""Portfolio ingestion and holdings/P&L computation."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..brokers import detect_broker
from ..brokers.base import BrokerAdapter, FileKind, NormalizedTransaction
from ..models import Account, Lot, Position, Transaction


def _get_or_create_account(db: Session, broker: str, label: str) -> Account:
    acct = db.execute(
        select(Account).where(Account.broker == broker, Account.account_label == label)
    ).scalar_one_or_none()
    if acct is None:
        acct = Account(broker=broker, account_label=label)
        db.add(acct)
        db.flush()
    return acct


def _txn_hash(account_id: int, t: NormalizedTransaction) -> str:
    key = "|".join(
        str(x)
        for x in (
            account_id,
            t.trade_date,
            t.ticker,
            t.action,
            t.quantity,
            t.price,
            t.amount,
            t.raw_description,
        )
    )
    return hashlib.sha256(key.encode()).hexdigest()


def ingest_csv(db: Session, text: str) -> dict:
    """Auto-detect broker + file kind, ingest, return a summary."""
    adapter, kind = detect_broker(text)
    if adapter is None or kind is None:
        return {"ok": False, "error": "Unrecognized CSV format. Expected a Fidelity or Merrill Edge positions/transactions export."}

    result = adapter.parse(text, kind)
    summary: dict = {
        "ok": True,
        "broker": adapter.broker_name,
        "kind": kind.value,
        "skipped_rows": len(result.skipped_rows),
    }

    if kind == FileKind.POSITIONS:
        labels = {p.account_label for p in result.positions} or {""}
        # Positions snapshots replace prior holdings for this broker's accounts.
        for label in labels:
            acct = _get_or_create_account(db, adapter.broker_name, label)
            db.execute(delete(Position).where(Position.account_id == acct.id))
        count = 0
        for p in result.positions:
            acct = _get_or_create_account(db, adapter.broker_name, p.account_label)
            db.add(
                Position(
                    account_id=acct.id,
                    ticker=p.ticker,
                    description=p.description,
                    quantity=p.quantity,
                    cost_basis=p.cost_basis,
                    last_price=p.last_price,
                    current_value=p.current_value,
                    asset_class=p.asset_class,
                    as_of_date=p.as_of_date,
                )
            )
            count += 1
        summary["positions_ingested"] = count
    else:
        existing = set(db.execute(select(Transaction.dedupe_hash)).scalars())
        inserted = duplicates = 0
        touched_accounts: set[int] = set()
        for t in result.transactions:
            acct = _get_or_create_account(db, adapter.broker_name, t.account_label)
            h = _txn_hash(acct.id, t)
            if h in existing:
                duplicates += 1
                continue
            existing.add(h)
            db.add(
                Transaction(
                    account_id=acct.id,
                    trade_date=t.trade_date,
                    settle_date=t.settle_date,
                    ticker=t.ticker,
                    action=t.action,
                    quantity=t.quantity,
                    price=t.price,
                    amount=t.amount,
                    fees=t.fees,
                    raw_description=t.raw_description,
                    dedupe_hash=h,
                )
            )
            touched_accounts.add(acct.id)
            inserted += 1
        summary["transactions_ingested"] = inserted
        summary["duplicates_skipped"] = duplicates
        db.flush()
        for account_id in touched_accounts:
            rebuild_lots(db, account_id)

    db.commit()
    return summary


def rebuild_lots(db: Session, account_id: int) -> None:
    """Recompute FIFO lots for an account from its buy/sell transactions."""
    db.execute(delete(Lot).where(Lot.account_id == account_id))
    txns = (
        db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id, Transaction.action.in_(["buy", "sell"]))
            .order_by(Transaction.trade_date)
        )
        .scalars()
        .all()
    )
    open_lots: dict[str, list[Lot]] = defaultdict(list)
    for t in txns:
        if not t.ticker or not t.quantity:
            continue
        qty = abs(t.quantity)
        if t.action == "buy":
            lot = Lot(
                account_id=account_id,
                ticker=t.ticker,
                open_date=t.trade_date,
                quantity=qty,
                cost_per_share=t.price,
            )
            open_lots[t.ticker].append(lot)
            db.add(lot)
        else:  # sell — consume FIFO
            remaining = qty
            for lot in open_lots[t.ticker]:
                if lot.closed or remaining <= 0:
                    continue
                take = min(lot.quantity, remaining)
                lot.quantity -= take
                remaining -= take
                if lot.quantity <= 1e-9:
                    lot.closed = True
    db.flush()


def get_holdings(db: Session) -> list[dict]:
    """All positions across accounts, aggregated by ticker."""
    rows = db.execute(select(Position, Account).join(Account)).all()
    by_ticker: dict[str, dict] = {}
    for pos, acct in rows:
        h = by_ticker.setdefault(
            pos.ticker,
            {
                "ticker": pos.ticker,
                "description": pos.description,
                "asset_class": pos.asset_class,
                "quantity": 0.0,
                "cost_basis": 0.0,
                "csv_value": 0.0,
                "csv_price": pos.last_price,
                "accounts": [],
            },
        )
        h["quantity"] += pos.quantity
        h["cost_basis"] += pos.cost_basis or 0.0
        h["csv_value"] += pos.current_value or 0.0
        label = f"{acct.broker}:{acct.account_label}" if acct.account_label else acct.broker
        if label not in h["accounts"]:
            h["accounts"].append(label)
    return list(by_ticker.values())
