import numpy as np
import pandas as pd
import pytest

from app.services.analytics import beta, series_metrics


def test_series_metrics_flat():
    returns = pd.Series([0.0] * 100)
    m = series_metrics(returns)
    assert m["annualized_return"] == pytest.approx(0.0)
    assert m["annualized_volatility"] == pytest.approx(0.0)
    assert m["sharpe"] is None
    assert m["max_drawdown"] == pytest.approx(0.0)


def test_series_metrics_constant_growth():
    daily = 0.001
    returns = pd.Series([daily] * 252)
    m = series_metrics(returns)
    assert m["annualized_return"] == pytest.approx((1 + daily) ** 252 - 1, rel=1e-6)
    assert m["max_drawdown"] == pytest.approx(0.0)


def test_max_drawdown():
    # +10%, then -50%: max drawdown is -50%
    returns = pd.Series([0.10, -0.50, 0.02])
    m = series_metrics(returns)
    assert m["max_drawdown"] == pytest.approx(-0.50)


def test_beta_of_market_is_one():
    rng = np.random.default_rng(42)
    market = pd.Series(rng.normal(0.0005, 0.01, 500))
    assert beta(market, market) == pytest.approx(1.0)


def test_beta_leveraged():
    rng = np.random.default_rng(7)
    market = pd.Series(rng.normal(0.0005, 0.01, 500))
    asset = market * 2.0
    assert beta(asset, market) == pytest.approx(2.0)


def test_beta_insufficient_data():
    assert beta(pd.Series([0.01]), pd.Series([0.02])) is None
