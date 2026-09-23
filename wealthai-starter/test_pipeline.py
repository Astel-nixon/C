"""Property-based checks on the pipeline.

Checks properties that matter -- weights sum to 1, constraints actually
hold, the frontier is monotonic, probabilities are bounded -- rather
than just "did it execute." Plain asserts with a small runner, printing
PASS/FAIL per check, consistent with the rest of this project's style.
"""

from __future__ import annotations

import traceback
from datetime import date

import universe
from client_profile import ClientProfile, Goal
from evidence import extract_evidence, validate_evidence
from explainability import generate_explanation
from goal_simulator import simulate_goal_probability
from house_view import prior_returns_series
from main import build_constraints
from portfolio_optimizer import Constraints, optimize_portfolio
from risk_engine import compute_risk_metrics
from stress_test import run_stress_tests
from tax import estimate_after_tax_return

EPS = 1e-6
_checks: list[tuple[str, callable]] = []


def check(name):
    def decorator(fn):
        _checks.append((name, fn))
        return fn

    return decorator


PRICES = universe.generate_universe_prices(years=5, seed=42)
CRYPTO_TICKERS = {t for t, c in universe.ASSET_CLASS_OF.items() if c == "Crypto"}
ILLIQUID_TICKERS = universe.illiquid_tickers()
PRIOR = prior_returns_series()


def _constraints(crypto_cap=0.05, illiquid_cap=0.20, min_cash=0.05, excluded=None):
    return Constraints(
        min_cash=min_cash, cash_ticker="CASH",
        group_caps={"Crypto": crypto_cap, "Illiquid": illiquid_cap},
        groups={"Crypto": CRYPTO_TICKERS, "Illiquid": ILLIQUID_TICKERS},
        excluded_tickers=excluded or set(),
    )


@check("weights sum to 1")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, constraints=_constraints(), expected_returns_prior=PRIOR)
    assert abs(sum(result.weights.values()) - 1.0) < 1e-3, sum(result.weights.values())


@check("crypto cap respected across risk tolerances")
def _():
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, constraints=_constraints(), expected_returns_prior=PRIOR)
        crypto_weight = sum(result.weights.get(t, 0.0) for t in CRYPTO_TICKERS)
        assert crypto_weight <= 0.05 + 1e-3, f"rt={rt} crypto={crypto_weight}"


@check("illiquid cap respected across risk tolerances")
def _():
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, constraints=_constraints(), expected_returns_prior=PRIOR)
        illiquid_weight = sum(result.weights.get(t, 0.0) for t in ILLIQUID_TICKERS)
        assert illiquid_weight <= 0.20 + 1e-3, f"rt={rt} illiquid={illiquid_weight}"


@check("cash floor respected across risk tolerances")
def _():
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, constraints=_constraints(), expected_returns_prior=PRIOR)
        cash_weight = result.weights.get("CASH", 0.0)
        assert cash_weight >= 0.05 - 1e-3, f"rt={rt} cash={cash_weight}"


@check("max position cap respected")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=1.0, constraints=_constraints(), expected_returns_prior=PRIOR)
    for ticker, weight in result.weights.items():
        if ticker != "CASH":
            assert weight <= 0.30 + 1e-3, f"{ticker}={weight}"


@check("ethical exclusions are respected")
def _():
    excluded = universe.tickers_matching_sectors(["tobacco", "weapons", "gambling"])
    assert excluded, "expected at least one instrument tagged for these sectors"
    result = optimize_portfolio(
        PRICES, risk_tolerance=0.7, constraints=_constraints(excluded=excluded), expected_returns_prior=PRIOR
    )
    for ticker in excluded:
        assert result.weights.get(ticker, 0.0) < 1e-3, f"{ticker} should be excluded"


@check("higher risk tolerance never produces lower volatility")
def _():
    prev_vol = -1.0
    for rt in (0.0, 0.25, 0.5, 0.75, 1.0):
        result = optimize_portfolio(PRICES, risk_tolerance=rt, constraints=_constraints(), expected_returns_prior=PRIOR)
        assert result.annual_volatility >= prev_vol - 1e-3, f"rt={rt} vol dropped vs prior step"
        prev_vol = result.annual_volatility


@check("frontier return is monotonic non-decreasing in volatility")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, constraints=_constraints(), expected_returns_prior=PRIOR, n_frontier_points=15)
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
    avg = (profile.risk_tolerance + profile.risk_capacity) / 2
    assert profile.effective_risk_score <= avg + 1e-9


@check("risk metrics are well-formed")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, constraints=_constraints(), expected_returns_prior=PRIOR)
    rm = compute_risk_metrics(PRICES, result.weights)
    assert rm["annual_volatility"] >= 0
    assert -1.0 <= rm["max_drawdown"] <= 0.0
    assert rm["var_95_daily"] >= 0
    assert rm["cvar_95_daily"] >= rm["var_95_daily"] - 1e-6


@check("stress test crypto crash scenario is non-positive when crypto held")
def _():
    result = optimize_portfolio(PRICES, risk_tolerance=1.0, constraints=_constraints(), expected_returns_prior=PRIOR)
    stress = run_stress_tests(result.weights)
    assert len(stress) == 6
    crypto_weight = sum(result.weights.get(t, 0.0) for t in CRYPTO_TICKERS)
    if crypto_weight > 0:
        assert stress["Crypto Crash (-70%)"] <= 0


@check("tax drag reduces net return, and zero-tax jurisdictions match the baseline")
def _():
    weights = {"US_EQUITY": 0.6, "GOVT_BONDS": 0.3, "CASH": 0.1}
    none_result = estimate_after_tax_return(weights, 0.08, jurisdiction="none")
    us_result = estimate_after_tax_return(weights, 0.08, jurisdiction="us_taxable")
    sg_result = estimate_after_tax_return(weights, 0.08, jurisdiction="singapore")
    assert none_result["total_tax_drag"] == 0.0
    assert us_result["total_tax_drag"] > 0.0
    assert us_result["net_expected_return"] < us_result["gross_expected_return"]
    assert sg_result["total_tax_drag"] == 0.0  # Singapore's real-world individual tax treatment


@check("evidence extractor produces schema-valid, bounded output")
def _():
    e = extract_evidence(
        "Company beats earnings guidance with record quarterly revenue growth.",
        source="test", timestamp="2026-01-01T00:00:00Z", ticker="US_EQUITY",
    )
    assert -1.0 <= e.sentiment <= 1.0
    assert 0.0 <= e.confidence <= 1.0
    assert e.event_type == "earnings"
    try:
        validate_evidence({"entity": "x", "event_type": "y", "sentiment": 5.0,
                            "source": "s", "timestamp": "t", "summary": "s"})
        raise AssertionError("should have rejected out-of-range sentiment")
    except ValueError:
        pass


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
    result = optimize_portfolio(PRICES, risk_tolerance=0.5, constraints=_constraints(), expected_returns_prior=PRIOR)
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


@check("full pipeline runs end to end for a client with a goal and exclusions")
def _():
    profile = ClientProfile(
        name="E2E", age=35, annual_income=120_000, net_worth=300_000, liquid_assets=200_000,
        risk_tolerance=0.7, investment_horizon_years=20, liquidity_need_years=5,
        income_stability=0.9, debt_to_income=0.1, excluded_sectors=["fossil_fuels"],
        tax_jurisdiction="us_taxable",
        goals=[Goal(name="Retirement", target_amount=2_000_000, target_date=date(2046, 1, 1))],
    )
    constraints = build_constraints(profile)
    result = optimize_portfolio(
        PRICES, risk_tolerance=profile.effective_risk_score, constraints=constraints,
        expected_returns_prior=PRIOR,
    )
    rm = compute_risk_metrics(PRICES, result.weights)
    stress = run_stress_tests(result.weights)
    tax_result = estimate_after_tax_return(result.weights, result.expected_annual_return, jurisdiction=profile.tax_jurisdiction)
    goal = profile.goals[0]
    sim = simulate_goal_probability(
        initial_capital=profile.liquid_assets, annual_contribution=profile.annual_income * 0.15,
        expected_return=tax_result["net_expected_return"], annual_volatility=result.annual_volatility,
        years=goal.years_remaining(), target_amount=goal.target_amount,
    )
    assert abs(sum(result.weights.values()) - 1.0) < 1e-3
    assert len(stress) == 6
    assert 0.0 <= sim["probability_of_success"] <= 1.0
    for excluded_ticker in universe.tickers_matching_sectors(["fossil_fuels"]):
        assert result.weights.get(excluded_ticker, 0.0) < 1e-3


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
