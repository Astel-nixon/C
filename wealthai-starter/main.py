"""Stage 1 research prototype entry point (master plan Part C / CLAUDE.md §2).

Runs two client profiles -- mirroring "Client A" (young, high risk
tolerance) and "Client B" (near-retirement, low risk tolerance) from the
master plan's Part A §2 -- through the full built pipeline:

    ClientProfile -> effective_risk_score -> portfolio optimizer
        -> risk engine -> stress tests -> goal simulation -> explanation

Same market data, same crypto/cash constraints, different risk profiles
-> different portfolios. That divergence is the whole point (see
CLAUDE.md Section 1).
"""

from __future__ import annotations

from datetime import date

from client_profile import ClientProfile, Goal
from data_source import get_prices
from explainability import generate_explanation
from goal_simulator import simulate_goal_probability
from portfolio_optimizer import PortfolioResult, optimize_portfolio
from risk_engine import compute_risk_metrics
from stress_test import run_stress_tests

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
    crypto_cap=0.05,
    min_cash=0.05,
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
    crypto_cap=0.05,
    min_cash=0.05,
)


def run_for_client(client: ClientProfile, prices) -> dict:
    result: PortfolioResult = optimize_portfolio(
        prices,
        risk_tolerance=client.effective_risk_score,
        crypto_cap=client.crypto_cap,
        min_cash=client.min_cash,
    )
    risk_metrics = compute_risk_metrics(prices, result.weights)
    stress_results = run_stress_tests(result.weights)

    goal = client.goals[0] if client.goals else None
    goal_result = None
    if goal is not None:
        goal_result = simulate_goal_probability(
            initial_capital=client.liquid_assets,
            annual_contribution=client.annual_income * 0.15,
            expected_return=result.expected_annual_return,
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
    )

    return {
        "portfolio": result,
        "risk_metrics": risk_metrics,
        "stress_results": stress_results,
        "goal_result": goal_result,
        "explanation": explanation,
    }


def print_report(client: ClientProfile, report: dict) -> None:
    result: PortfolioResult = report["portfolio"]
    print(
        f"\n=== {client.name} (age {client.age}, tolerance={client.risk_tolerance:.2f}, "
        f"capacity={client.risk_capacity:.2f}, effective={client.effective_risk_score:.2f}) ==="
    )
    for asset, weight in sorted(result.weights.items(), key=lambda kv: -kv[1]):
        if weight > 0.0001:
            print(f"  {asset:<18} {weight:6.1%}")
    print(f"  Expected annual return: {result.expected_annual_return:6.1%}")
    print(f"  Annual volatility:      {result.annual_volatility:6.1%}")
    print(f"  Sharpe ratio:           {result.sharpe_ratio:6.2f}")

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
    print(f"Generated {len(prices)} days of prices for: {list(prices.columns)}")

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
