"""Mean-variance portfolio construction (Part A §14 / §11).

Uses PyPortfolioOpt: Ledoit-Wolf shrinkage for the covariance estimate
(raw sample covariance is noisy with only a few years of history — see
the estimation-error finding in the master plan's Part C §C2), and a
constrained EfficientFrontier solver for the actual allocation.

Client risk tolerance selects *where on the efficient frontier* the
recommendation lands, rather than always returning the single max-Sharpe
(tangency) portfolio. That is the fix described in Part C §C4: without
it, two clients with different risk tolerance but the same crypto/cash
constraints would get an identical portfolio, which contradicts the
platform's central premise (Part A §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pypfopt import EfficientFrontier, risk_models
from pypfopt.exceptions import OptimizationError
from pypfopt.expected_returns import mean_historical_return


@dataclass
class PortfolioResult:
    weights: dict[str, float]
    expected_annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    risk_tolerance: float
    frontier: list[tuple[float, float]] = field(default_factory=list)


def _build_ef(
    prices: pd.DataFrame,
    crypto_cap: float,
    min_cash: float,
    risk_free_rate: float,
) -> EfficientFrontier:
    """Fresh EfficientFrontier instance with client constraints applied.

    PyPortfolioOpt solvers mutate internal state on each solve call, so a
    new instance is built per optimization rather than reused.
    """
    mu = mean_historical_return(prices)
    cov = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

    ef = EfficientFrontier(mu, cov)

    if "Crypto" in prices.columns:
        ef.add_constraint(lambda w: w[prices.columns.get_loc("Crypto")] <= crypto_cap)
    if "Cash" in prices.columns:
        ef.add_constraint(lambda w: w[prices.columns.get_loc("Cash")] >= min_cash)

    return ef


def _max_feasible_return(
    prices: pd.DataFrame, crypto_cap: float, min_cash: float, risk_free_rate: float
) -> float:
    """Binary-search the highest target return still feasible under constraints.

    Needed because the unconstrained highest-mu asset (Crypto) is capped, so
    the true max-return corner of the constrained frontier isn't just
    ``mu.max()``.
    """
    mu = mean_historical_return(prices)
    lo, hi = float(mu.min()), float(mu.max())
    best = lo
    for _ in range(30):
        mid = (lo + hi) / 2
        ef = _build_ef(prices, crypto_cap, min_cash, risk_free_rate)
        try:
            ef.efficient_return(target_return=mid)
            best = mid
            lo = mid
        except (OptimizationError, ValueError):
            hi = mid
    return best


def optimize_portfolio(
    prices: pd.DataFrame,
    risk_tolerance: float = 0.5,
    crypto_cap: float = 0.05,
    min_cash: float = 0.05,
    risk_free_rate: float = 0.02,
    n_frontier_points: int = 15,
) -> PortfolioResult:
    """Solve for the client's allocation at a target point on the frontier.

    risk_tolerance in [0, 1]: 0 -> minimum-volatility portfolio,
    1 -> highest-return portfolio still feasible under the client's
    constraints (crypto cap, cash floor). Values in between linearly
    interpolate the target volatility between those two endpoints.
    """
    if not 0.0 <= risk_tolerance <= 1.0:
        raise ValueError("risk_tolerance must be in [0, 1]")

    ef_min = _build_ef(prices, crypto_cap, min_cash, risk_free_rate)
    min_vol_weights = ef_min.min_volatility()
    _, vol_min, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

    max_return = _max_feasible_return(prices, crypto_cap, min_cash, risk_free_rate)
    ef_max = _build_ef(prices, crypto_cap, min_cash, risk_free_rate)
    ef_max.efficient_return(target_return=max_return)
    _, vol_max, _ = ef_max.portfolio_performance(risk_free_rate=risk_free_rate)

    target_vol = vol_min + risk_tolerance * (vol_max - vol_min)

    if risk_tolerance <= 0.0:
        weights, perf_source = min_vol_weights, ef_min
    elif risk_tolerance >= 1.0:
        weights, perf_source = ef_max.clean_weights(), ef_max
    else:
        ef = _build_ef(prices, crypto_cap, min_cash, risk_free_rate)
        try:
            weights = ef.efficient_risk(target_volatility=target_vol)
        except OptimizationError:
            # Target vol fell just outside the feasible region due to solver
            # tolerance at the boundary; fall back to the nearer endpoint.
            weights = min_vol_weights if risk_tolerance < 0.5 else ef_max.clean_weights()
        perf_source = ef

    ret, vol, sharpe = perf_source.portfolio_performance(risk_free_rate=risk_free_rate)

    frontier = efficient_frontier_points(
        prices, crypto_cap, min_cash, risk_free_rate, n_frontier_points, vol_min, vol_max
    )

    return PortfolioResult(
        weights={k: round(v, 4) for k, v in weights.items()},
        expected_annual_return=ret,
        annual_volatility=vol,
        sharpe_ratio=sharpe,
        risk_tolerance=risk_tolerance,
        frontier=frontier,
    )


def efficient_frontier_points(
    prices: pd.DataFrame,
    crypto_cap: float,
    min_cash: float,
    risk_free_rate: float,
    n_points: int,
    vol_min: float,
    vol_max: float,
) -> list[tuple[float, float]]:
    """(volatility, return) pairs along the constrained frontier, for plotting."""
    points: list[tuple[float, float]] = []
    if n_points <= 0 or vol_max <= vol_min:
        return points
    for i in range(n_points):
        target = vol_min + (vol_max - vol_min) * i / (n_points - 1)
        ef = _build_ef(prices, crypto_cap, min_cash, risk_free_rate)
        try:
            ef.efficient_risk(target_volatility=target)
            ret, vol, _ = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            points.append((vol, ret))
        except OptimizationError:
            continue
    return points
