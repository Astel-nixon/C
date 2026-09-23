"""Risk engine (master plan Part A §17).

Metrics computed directly on the chosen portfolio's own realized daily
return series (weights applied to actual historical prices) -- not
assumed from the optimizer's own mean/covariance estimate. Formulas are
hand-implemented rather than pulled from a dependency: the set is small
enough that direct code is easier to audit than a library boundary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def portfolio_returns(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    daily_returns = prices.pct_change().dropna()
    w = np.array([weights.get(col, 0.0) for col in daily_returns.columns])
    return daily_returns.dot(w)


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.02, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    excess = returns - risk_free_rate / periods_per_year
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series, risk_free_rate: float = 0.02, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    excess = returns - risk_free_rate / periods_per_year
    downside = excess[excess < 0]
    downside_std = downside.std()
    if not downside_std or np.isnan(downside_std) or downside_std == 0:
        return 0.0
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min())


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """One-day VaR as a positive loss fraction at the given confidence level."""
    return float(-np.percentile(returns, (1 - confidence) * 100))


def conditional_value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Expected Shortfall: mean loss in the tail beyond VaR, as a positive fraction."""
    var = value_at_risk(returns, confidence)
    tail = returns[returns <= -var]
    if len(tail) == 0:
        return var
    return float(-tail.mean())


def compute_risk_metrics(
    prices: pd.DataFrame, weights: dict[str, float], risk_free_rate: float = 0.02
) -> dict[str, float]:
    returns = portfolio_returns(prices, weights)
    return {
        "sharpe_ratio": sharpe_ratio(returns, risk_free_rate),
        "sortino_ratio": sortino_ratio(returns, risk_free_rate),
        "max_drawdown": max_drawdown(returns),
        "var_95_daily": value_at_risk(returns, 0.95),
        "cvar_95_daily": conditional_value_at_risk(returns, 0.95),
        "annual_volatility": float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)),
    }
