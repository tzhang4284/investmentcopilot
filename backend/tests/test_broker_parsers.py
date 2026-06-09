from pathlib import Path

import pytest

from app.brokers import FileKind, detect_broker
from app.brokers.base import to_float

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize(
    "filename,broker,kind",
    [
        ("fidelity_positions.csv", "fidelity", FileKind.POSITIONS),
        ("fidelity_transactions.csv", "fidelity", FileKind.TRANSACTIONS),
        ("merrill_positions.csv", "merrill", FileKind.POSITIONS),
        ("merrill_transactions.csv", "merrill", FileKind.TRANSACTIONS),
    ],
)
def test_detection(filename, broker, kind):
    adapter, detected_kind = detect_broker(load(filename))
    assert adapter is not None, f"failed to detect {filename}"
    assert adapter.broker_name == broker
    assert detected_kind == kind


def test_to_float():
    assert to_float("$1,234.56") == 1234.56
    assert to_float('"1,234.56"') == 1234.56
    assert to_float("(123.45)") == -123.45
    assert to_float("--") is None
    assert to_float("n/a") is None
    assert to_float("") is None
    assert to_float("+0.60%") == 0.60
    assert to_float("123-") == -123.0


def test_fidelity_positions():
    adapter, kind = detect_broker(load("fidelity_positions.csv"))
    result = adapter.parse(load("fidelity_positions.csv"), kind)
    tickers = {p.ticker for p in result.positions}
    assert {"AAPL", "MSFT", "NVDA", "GOOGL", "BRK/B"} <= tickers
    aapl = next(p for p in result.positions if p.ticker == "AAPL")
    assert aapl.quantity == 50
    assert aapl.cost_basis == 7500.00
    assert aapl.last_price == 201.50
    assert aapl.current_value == 10075.00
    # SPAXX** money market → cash with $ value as quantity
    spaxx = next(p for p in result.positions if p.ticker.startswith("SPAXX"))
    assert spaxx.asset_class == "cash"
    assert spaxx.quantity == pytest.approx(6789.12)
    # Footer disclaimer rows must not become positions
    assert all("data and information" not in p.ticker.lower() for p in result.positions)


def test_fidelity_transactions():
    adapter, kind = detect_broker(load("fidelity_transactions.csv"))
    result = adapter.parse(load("fidelity_transactions.csv"), kind)
    actions = [t.action for t in result.transactions]
    assert "buy" in actions and "sell" in actions and "dividend" in actions
    buy = next(t for t in result.transactions if t.action == "buy" and t.ticker == "NVDA")
    assert buy.quantity == 10
    assert buy.price == 132.50
    assert buy.amount == -1325.00
    assert buy.trade_date.isoformat() == "2026-06-02"
    sell = next(t for t in result.transactions if t.action == "sell")
    assert sell.ticker == "MSFT"
    assert sell.amount == 2240.47


def test_merrill_positions():
    adapter, kind = detect_broker(load("merrill_positions.csv"))
    result = adapter.parse(load("merrill_positions.csv"), kind)
    tickers = {p.ticker for p in result.positions}
    assert {"AMZN", "JPM", "XOM", "UNH"} <= tickers
    xom = next(p for p in result.positions if p.ticker == "XOM")
    assert xom.quantity == 45
    assert xom.cost_basis == 5736.00
    # Footer Total/Pending rows skipped
    assert "TOTAL" not in {p.ticker.upper() for p in result.positions}
    assert len(result.skipped_rows) >= 2


def test_merrill_transactions():
    adapter, kind = detect_broker(load("merrill_transactions.csv"))
    result = adapter.parse(load("merrill_transactions.csv"), kind)
    buy = next(t for t in result.transactions if t.action == "buy" and t.ticker == "AMZN")
    assert buy.quantity == 10
    assert buy.amount == -1821.50  # parenthesized negative
    div = next(t for t in result.transactions if t.action == "dividend")
    assert div.ticker == "JPM"
    assert div.amount == 32.20
    deposit = next(t for t in result.transactions if t.action == "transfer")
    assert deposit.amount == 15000.00
