"""Property-based checks on the pipeline (CLAUDE.md Section 3/4 Principle 5).

Checks properties that matter -- weights sum to 1, constraints actually
hold, the frontier is monotonic, probabilities are bounded -- rather
than just "did it execute." Plain asserts with a small runner, printing
PASS/FAIL per check, consistent with the rest of this prototype's style.
"""

from __future__ import annotations

import traceback
from datetime import date

from client_profile import ClientProfile, Goal
from explainability import generate_explanation
from goal_simulator import simulate_goal_probability
from portfolio_optimizer import optimize_portfolio
from risk_engine import compute_risk_metrics
from stress_test import run_stress_tests
from synthetic_data import generate_synthetic_prices

EPS = 1e-6
_checks: list[tuple[str, callable]] = []


def check(name):
    def decorator(fn):
        _checks.append((name, fn))
        return fn

    return decorator


PRICES = generate_synthetic_prices(years=5, seed=42)


@check("weights sum to 1")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, crypto_cap=0.05, min_cash=0.05)
    assert abs(sum(result.weights.values()) - 1.0) < 1e-3, sum(result.weights.values())


@check("crypto cap respected across risk tolerances")
def _():
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, crypto_cap=0.05, min_cash=0.05)
        crypto_weight = result.weights.get("Crypto", 0.0)
        assert crypto_weight <= 0.05 + 1e-3, f"rt={rt} crypto={crypto_weight}"


@check("cash floor respected across risk tolerances")
def _():
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, crypto_cap=0.05, min_cash=0.05)
        cash_weight = result.weights.get("Cash", 0.0)
        assert cash_weight >= 0.05 - 1e-3, f"rt={rt} cash={cash_weight}"


@check("higher risk tolerance never produces lower volatility")
def _():
    prev_vol = -1.0
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, crypto_cap=0.05, min_cash=0.05)
        assert result.annual_volatility >= prev_vol - 1e-3, f"rt={rt} vol dropped vs prior step"
        prev_vol = result.annual_volatility


@check("frontier return is monotonic non-decreasing in volatility")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, n_frontier_points=15)
    assert len(result.frontier) >= 2, "not enough frontier points computed"
    sorted_pts = sorted(result.frontier, key=lambda p: p[0])
    prev_ret = -1e9
    for vol, ret in sorted_pts:
        assert ret >= prev_ret - 1e-6, f"return decreased along frontier: {sorted_pts}"
        prev_ret = ret


@check("risk capacity caps tolerance, never averages it")
def _():
    profile = ClientProfile(
        name="X", age=40, annual_income=100_000, net_worth=500_000, liquid_assets=400_000,
        risk_tolerance=0.95, investment_horizon_years=2, liquidity_need_years=1,
        income_stability=0.3, debt_to_income=0.6,
    )
    assert profile.effective_risk_score <= profile.risk_tolerance
    assert profile.effective_risk_score <= profile.risk_capacity
    # Explicitly not the average of the two.
    avg = (profile.risk_tolerance + profile.risk_capacity) / 2
    assert profile.effective_risk_score <= avg + 1e-9


@check("risk metrics are well-formed")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5)
    rm = compute_risk_metrics(PRICES, result.weights)
    assert rm["annual_volatility"] >= 0
    assert -1.0 <= rm["max_drawdown"] <= 0.0
    assert rm["var_95_daily"] >= 0  # positive loss magnitude by convention
    assert rm["cvar_95_daily"] >= rm["var_95_daily"] - 1e-6  # ES >= VaR in magnitude


@check("stress test crypto crash scenario is non-positive when crypto held")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=1.0, crypto_cap=0.05, min_cash=0.05)
    stress = run_stress_tests(result.weights)
    if result.weights.get("Crypto", 0.0) > 0:
        assert stress["Crypto Crash (-70%)"] <= 0


@check("goal simulation probability is bounded 0..1")
def _():
    sim = simulate_goal_probability(
        initial_capital=100_000, annual_contribution=20_000, expected_return=0.07,
        annual_volatility=0.15, years=20, target_amount=1_000_000,
    )
    assert 0.0 <= sim["probability_of_success"] <= 1.0
    assert sim["percentiles"][5] <= sim["percentiles"][50] <= sim["percentiles"][95]


@check("goal simulation: near-zero years still returns a valid result")
def _():
    sim = simulate_goal_probability(
        initial_capital=100_000, annual_contribution=0, expected_return=0.07,
        annual_volatility=0.15, years=0, target_amount=90_000,
    )
    assert 0.0 <= sim["probability_of_success"] <= 1.0


@check("explanation is non-empty and mentions the client")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5)
    rm = compute_risk_metrics(PRICES, result.weights)
    text = generate_explanation(
        client_name="Test Client", effective_risk_score=0.5, risk_tolerance=0.5,
        risk_capacity=0.6, weights=result.weights,
        expected_annual_return=result.expected_annual_return,
        annual_volatility=result.annual_volatility, sharpe_ratio=result.sharpe_ratio,
        risk_metrics=rm,
    )
    assert "Test Client" in text
    assert len(text) > 20


@check("full pipeline runs end to end for a client with a goal")
def _():
    profile = ClientProfile(
        name="E2E", age=35, annual_income=120_000, net_worth=300_000, liquid_assets=200_000,
        risk_tolerance=0.7, investment_horizon_years=20, liquidity_need_years=5,
        income_stability=0.9, debt_to_income=0.1,
        goals=[Goal(name="Retirement", target_amount=2_000_000, target_date=date(2046, 1, 1))],
    )
    result = optimize_portfolio(PRICES, risk_tolerance=profile.effective_risk_score,
                                 crypto_cap=profile.crypto_cap, min_cash=profile.min_cash)
    rm = compute_risk_metrics(PRICES, result.weights)
    stress = run_stress_tests(result.weights)
    goal = profile.goals[0]
    sim = simulate_goal_probability(
        initial_capital=profile.liquid_assets, annual_contribution=profile.annual_income * 0.15,
        expected_return=result.expected_annual_return, annual_volatility=result.annual_volatility,
        years=goal.years_remaining(), target_amount=goal.target_amount,
    )
    assert abs(sum(result.weights.values()) - 1.0) < 1e-3
    assert len(stress) == 5
    assert 0.0 <= sim["probability_of_success"] <= 1.0


def run_all() -> int:
    passed = failed = 0
    for name, fn in _checks:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
        except Exception:
            print(f"  ERROR {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {len(_checks)} total")
    return failed


if __name__ == "__main__":
    import sys

    sys.exit(1 if run_all() else 0)
