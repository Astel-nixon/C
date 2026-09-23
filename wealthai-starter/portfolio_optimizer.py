"""Mean-variance portfolio construction over the full instrument universe.

Ledoit-Wolf shrinkage for the covariance estimate (raw sample covariance
gets noisy fast once the universe is 20+ instruments and history is a
few years -- see the estimation-error discussion in the project notes),
and a constrained EfficientFrontier solver for the actual allocation.

Constraints are expressed generically as named ticker groups with a cap
on total weight -- `groups={"Crypto": {"BITCOIN","ETHEREUM"}, "Illiquid":
{...}}`, `group_caps={"Crypto": 0.05, "Illiquid": 0.20}` -- rather than
hardcoding what "crypto" or "illiquid" means inside this module. That
keeps the optimizer itself asset-agnostic: universe.py decides which
tickers belong to which group (by asset class, by liquidity tier, by
ethical exclusion), this module just enforces whatever caps it's given.

Client risk tolerance selects *where on the efficient frontier* the
recommendation lands, rather than always returning the single max-Sharpe
(tangency) portfolio -- interpolating target volatility between the
minimum-volatility portfolio and the highest return still feasible
under the client's constraints. Without that, two clients with
different risk tolerance but the same constraints would get an
identical portfolio, which defeats the entire point of a personalized
plan in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pypfopt import EfficientFrontier, risk_models
from pypfopt.exceptions import OptimizationError

from estimators import shrunk_expected_returns


@dataclass
class PortfolioResult:
    weights: dict[str, float]
    expected_annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    risk_tolerance: float
    frontier: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Constraints:
    """Everything about a client that shapes the feasible region, decoupled
    from risk_tolerance (which only picks a point within that region)."""

    min_cash: float = 0.05
    cash_ticker: str = "CASH"
    group_caps: dict[str, float] = field(default_factory=dict)
    groups: dict[str, set[str]] = field(default_factory=dict)
    excluded_tickers: set[str] = field(default_factory=set)
    # No single line item above this share of the portfolio, cash aside --
    # a plain concentration limit. Without it, a single noisy return
    # estimate can end up dominating the whole allocation (see estimators.py);
    # this is also just standard prudent-investor practice on its own.
    max_position: float = 0.30


def _build_ef(prices: pd.DataFrame, c: Constraints, prior: pd.Series | None) -> EfficientFrontier:
    """Fresh EfficientFrontier instance with client constraints applied.

    PyPortfolioOpt solvers mutate internal state on each solve call, so a
    new instance is built per optimization rather than reused.
    """
    mu = shrunk_expected_returns(prices, prior=prior)
    cov = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

    ef = EfficientFrontier(mu, cov)
    columns = list(prices.columns)

    if c.max_position < 1.0:
        for i, ticker in enumerate(columns):
            if ticker != c.cash_ticker:
                ef.add_constraint(lambda w, i=i: w[i] <= c.max_position)

    for ticker in c.excluded_tickers:
        if ticker in columns:
            i = columns.index(ticker)
            ef.add_constraint(lambda w, i=i: w[i] <= 0)

    for group_name, cap in c.group_caps.items():
        member_tickers = c.groups.get(group_name, set())
        idxs = [columns.index(t) for t in member_tickers if t in columns]
        if idxs:
            ef.add_constraint(lambda w, idxs=idxs, cap=cap: sum(w[i] for i in idxs) <= cap)

    if c.cash_ticker in columns:
        i = columns.index(c.cash_ticker)
        ef.add_constraint(lambda w, i=i: w[i] >= c.min_cash)

    return ef


def _max_feasible_return(prices: pd.DataFrame, c: Constraints, prior: pd.Series | None) -> float:
    """Binary-search the highest target return still feasible under constraints.

    Needed because the highest-mu instrument is usually the one that's
    capped (crypto, most likely), so the true max-return corner of the
    constrained frontier isn't just mu.max().

    With heavily shrunk returns (see estimators.py), mu.min() and mu.max()
    can sit almost exactly on top of each other, and cvxpy's own LP solve
    can land a hair below the externally computed mu.max() due to plain
    floating-point noise -- that first attempt would fail every time, and
    a naive bisection that sets hi = mid on failure makes no progress when
    mid already equals hi. Nudging hi down by a small amount on every
    failure guarantees the search actually shrinks, even in that
    near-degenerate case.
    """
    mu = shrunk_expected_returns(prices, prior=prior)
    lo, hi = float(mu.min()), float(mu.max())
    spread = max(hi - lo, 1e-6)
    best = lo
    for _ in range(30):
        mid = (lo + hi) / 2
        ef = _build_ef(prices, c, prior)
        try:
            ef.efficient_return(target_return=mid)
            best = mid
            lo = mid
        except (OptimizationError, ValueError):
            hi = mid - spread * 1e-3
    return best


def optimize_portfolio(
    prices: pd.DataFrame,
    risk_tolerance: float = 0.5,
    constraints: Constraints | None = None,
    expected_returns_prior: pd.Series | None = None,
    risk_free_rate: float = 0.02,
    n_frontier_points: int = 15,
) -> PortfolioResult:
    """Solve for the client's allocation at a target point on the frontier.

    risk_tolerance in [0, 1]: 0 -> minimum-volatility portfolio,
    1 -> highest-return portfolio still feasible under `constraints`.
    Values in between linearly interpolate the target volatility between
    those two endpoints.

    expected_returns_prior (optional): what the shrinkage estimator pulls
    noisy sample means toward -- see estimators.py and house_view.py.
    Defaults to the cross-sectional grand mean when not supplied.
    """
    if not 0.0 <= risk_tolerance <= 1.0:
        raise ValueError("risk_tolerance must be in [0, 1]")
    c = constraints or Constraints()
    prior = expected_returns_prior

    ef_min = _build_ef(prices, c, prior)
    min_vol_weights = ef_min.min_volatility()
    _, vol_min, _ = ef_min.portfolio_performance(risk_free_rate=risk_free_rate)

    max_return = _max_feasible_return(prices, c, prior)
    ef_max = _build_ef(prices, c, prior)
    try:
        ef_max.efficient_return(target_return=max_return)
    except OptimizationError:
        # Near-degenerate expected returns (heavy shrinkage collapsing most
        # assets to about the same mu) can leave no well-defined "highest
        # return" corner -- every feasible portfolio ties. Sharpe-optimal
        # is the next-best-posed fallback; minimum volatility after that.
        try:
            ef_max = _build_ef(prices, c, prior)
            ef_max.max_sharpe(risk_free_rate=risk_free_rate)
        except OptimizationError:
            ef_max = _build_ef(prices, c, prior)
            ef_max.min_volatility()
    _, vol_max, _ = ef_max.portfolio_performance(risk_free_rate=risk_free_rate)

    target_vol = vol_min + risk_tolerance * (vol_max - vol_min)

    if risk_tolerance <= 0.0:
        weights, perf_source = min_vol_weights, ef_min
    elif risk_tolerance >= 1.0:
        weights, perf_source = ef_max.clean_weights(), ef_max
    else:
        ef = _build_ef(prices, c, prior)
        try:
            weights = ef.efficient_risk(target_volatility=target_vol)
        except OptimizationError:
            # Target vol fell just outside the feasible region due to solver
            # tolerance at the boundary; fall back to the nearer endpoint.
            weights = min_vol_weights if risk_tolerance < 0.5 else ef_max.clean_weights()
        perf_source = ef

    ret, vol, sharpe = perf_source.portfolio_performance(risk_free_rate=risk_free_rate)

    frontier = efficient_frontier_points(
        prices, c, prior, n_frontier_points, vol_min, vol_max, risk_free_rate
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
    constraints: Constraints,
    prior: pd.Series | None,
    n_points: int,
    vol_min: float,
    vol_max: float,
    risk_free_rate: float = 0.02,
) -> list[tuple[float, float]]:
    """(volatility, return) pairs along the constrained frontier, for plotting."""
    points: list[tuple[float, float]] = []
    if n_points <= 0 or vol_max <= vol_min:
        return points
    for i in range(n_points):
        target = vol_min + (vol_max - vol_min) * i / (n_points - 1)
        ef = _build_ef(prices, constraints, prior)
        try:
            ef.efficient_risk(target_volatility=target)
            ret, vol, _ = ef.portfolio_performance(risk_free_rate=risk_free_rate)
            points.append((vol, ret))
        except OptimizationError:
            continue
    return points
