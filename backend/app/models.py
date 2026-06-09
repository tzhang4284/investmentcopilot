from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker: Mapped[str] = mapped_column(String(32))  # "fidelity" | "merrill"
    account_label: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (UniqueConstraint("broker", "account_label", name="uq_account"),)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(String(256), default="")
    quantity: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)  # total $
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # from CSV
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    asset_class: Mapped[str] = mapped_column(String(24), default="equity")  # equity|cash|fund|other
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settle_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True, default="")
    action: Mapped[str] = mapped_column(String(24))  # buy|sell|dividend|interest|reinvest|transfer|other
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_description: Mapped[str] = mapped_column(String(512), default="")
    dedupe_hash: Mapped[str] = mapped_column(String(64), unique=True)


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    open_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    cost_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    direction: Mapped[str] = mapped_column(String(8), default="long")  # long|short
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_horizon_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thesis_text: Mapped[str] = mapped_column(Text, default="")
    catalysts: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    conviction: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|closed
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Memo(Base):
    __tablename__ = "memos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content_md: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InsiderTransaction(Base):
    __tablename__ = "insider_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(24), index=True)
    cik: Mapped[str] = mapped_column(String(16), default="")
    insider_name: Mapped[str] = mapped_column(String(128))
    insider_title: Mapped[str] = mapped_column(String(128), default="")
    is_director: Mapped[bool] = mapped_column(Boolean, default=False)
    is_officer: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_code: Mapped[str] = mapped_column(String(4))  # P, S, A, D, G, F, M...
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    accession_no: Mapped[str] = mapped_column(String(32))
    row_index: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("accession_no", "row_index", name="uq_insider_txn"),
    )


class MarketCache(Base):
    __tablename__ = "market_cache"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)  # JSON
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
