"""Entry point: run client profiles through the full built pipeline.

    ClientProfile -> constraints (crypto cap, illiquidity cap, ethical
        exclusions, cash floor) -> effective_risk_score -> portfolio
        optimizer -> risk engine -> stress tests -> goal simulation ->
        tax drag -> explanation

Two example clients -- mirroring "Client A" (young, high risk
tolerance) and "Client B" (near-retirement, low risk tolerance) from
the original project brief -- run through identical market data and
constraints structure but different profiles. That the two portfolios
come out different is the point: same market, different investor,
different plan.
"""

from __future__ import annotations

from datetime import date

import universe
from client_profile import ClientProfile, Goal
from data_source import get_prices
from explainability import generate_explanation
from goal_simulator import simulate_goal_probability
from house_view import prior_returns_series
from portfolio_optimizer import Constraints, PortfolioResult, optimize_portfolio
from risk_engine import compute_risk_metrics
from stress_test import run_stress_tests
from tax import estimate_after_tax_return

CLIENT_A = ClientProfile(
    name="Client A",
    age=28,
    annual_income=150_000,
    net_worth=180_000,
    liquid_assets=120_000,
    risk_tolerance=0.85,
    investment_horizon_years=30,
    liquidity_need_years=8,
    income_stability=0.8,
    debt_to_income=0.15,
    goals=[Goal(name="Retirement", target_amount=2_500_000, target_date=date(2056, 1, 1))],
    crypto_cap=0.08,
    illiquid_cap=0.25,
    min_cash=0.05,
    tax_jurisdiction="us_taxable",
)

CLIENT_B = ClientProfile(
    name="Client B",
    age=57,
    annual_income=180_000,
    net_worth=1_400_000,
    liquid_assets=900_000,
    risk_tolerance=0.55,
    investment_horizon_years=7,
    liquidity_need_years=2,
    income_stability=0.7,
    debt_to_income=0.05,
    goals=[Goal(name="Retirement", target_amount=1_800_000, target_date=date(2033, 1, 1))],
    crypto_cap=0.03,
    illiquid_cap=0.15,
    min_cash=0.08,
    excluded_sectors=["tobacco", "weapons"],
    tax_jurisdiction="singapore",
)


def build_constraints(client: ClientProfile) -> Constraints:
    """Turn a client profile into the concrete feasible region the
    optimizer solves over -- the only place client fields get translated
    into universe.py's ticker groupings."""
    crypto_tickers = {t for t, cls in universe.ASSET_CLASS_OF.items() if cls == "Crypto"}
    illiquid_tickers = universe.illiquid_tickers()
    return Constraints(
        min_cash=client.min_cash,
        cash_ticker="CASH",
        group_caps={"Crypto": client.crypto_cap, "Illiquid": client.illiquid_cap},
        groups={"Crypto": crypto_tickers, "Illiquid": illiquid_tickers},
        excluded_tickers=universe.tickers_matching_sectors(client.excluded_sectors),
    )


def run_for_client(client: ClientProfile, prices) -> dict:
    constraints = build_constraints(client)
    result: PortfolioResult = optimize_portfolio(
        prices, risk_tolerance=client.effective_risk_score, constraints=constraints,
        expected_returns_prior=prior_returns_series(),
    )
    risk_metrics = compute_risk_metrics(prices, result.weights)
    stress_results = run_stress_tests(result.weights)
    tax_result = estimate_after_tax_return(
        result.weights, result.expected_annual_return, jurisdiction=client.tax_jurisdiction,
    )

    goal = client.goals[0] if client.goals else None
    goal_result = None
    if goal is not None:
        goal_result = simulate_goal_probability(
            initial_capital=client.liquid_assets,
            annual_contribution=client.annual_income * 0.15,
            expected_return=tax_result["net_expected_return"],
            annual_volatility=result.annual_volatility,
            years=goal.years_remaining(),
            target_amount=goal.target_amount,
        )

    explanation = generate_explanation(
        client_name=client.name,
        effective_risk_score=client.effective_risk_score,
        risk_tolerance=client.risk_tolerance,
        risk_capacity=client.risk_capacity,
        weights=result.weights,
        expected_annual_return=result.expected_annual_return,
        annual_volatility=result.annual_volatility,
        sharpe_ratio=result.sharpe_ratio,
        risk_metrics=risk_metrics,
        goal_result=goal_result,
        excluded_sectors=client.excluded_sectors,
        tax_result=tax_result,
    )

    return {
        "portfolio": result,
        "risk_metrics": risk_metrics,
        "stress_results": stress_results,
        "goal_result": goal_result,
        "tax_result": tax_result,
        "explanation": explanation,
    }


def print_report(client: ClientProfile, report: dict) -> None:
    result: PortfolioResult = report["portfolio"]
    print(
        f"\n=== {client.name} (age {client.age}, tolerance={client.risk_tolerance:.2f}, "
        f"capacity={client.risk_capacity:.2f}, effective={client.effective_risk_score:.2f}) ==="
    )
    for ticker, weight in sorted(result.weights.items(), key=lambda kv: -kv[1]):
        if weight > 0.0005:
            name = next((i.name for i in universe.UNIVERSE if i.ticker == ticker), ticker)
            print(f"  {name:<32} {weight:6.1%}")
    print(f"  Expected annual return (gross): {result.expected_annual_return:6.1%}")
    print(f"  Annual volatility:              {result.annual_volatility:6.1%}")
    print(f"  Sharpe ratio:                   {result.sharpe_ratio:6.2f}")

    tr = report["tax_result"]
    print(
        f"  Tax drag ({tr['jurisdiction_label']}): -{tr['total_tax_drag']:.2%} -> "
        f"net expected return {tr['net_expected_return']:.1%}"
    )

    rm = report["risk_metrics"]
    print(
        f"  Sortino: {rm['sortino_ratio']:.2f}  Max drawdown: {rm['max_drawdown']:.1%}  "
        f"VaR(95,1d): {rm['var_95_daily']:.1%}  CVaR(95,1d): {rm['cvar_95_daily']:.1%}"
    )

    print("  Stress scenarios:")
    for scenario, impact in report["stress_results"].items():
        print(f"    {scenario:<24} {impact:+.1%}")

    if report["goal_result"]:
        gr = report["goal_result"]
        print(
            f"  Goal probability of success: {gr['probability_of_success']:.0%} "
            f"(median outcome ${gr['median_outcome']:,.0f} vs target ${gr['target_amount']:,.0f})"
        )

    print(f"\n  {report['explanation']}")


def main() -> None:
    prices, data_version = get_prices(years=5, seed=42)
    print(f"Data source: {data_version}")
    print(f"{len(prices.columns)} instruments across the universe: {list(prices.columns)}")

    report_a = run_for_client(CLIENT_A, prices)
    report_b = run_for_client(CLIENT_B, prices)

    print_report(CLIENT_A, report_a)
    print_report(CLIENT_B, report_b)

    vol_a = report_a["portfolio"].annual_volatility
    vol_b = report_b["portfolio"].annual_volatility
    print(
        f"\nSame market data, different risk profiles -> different portfolios: "
        f"{vol_a:.1%} vol vs {vol_b:.1%} vol."
    )


if __name__ == "__main__":
    main()
