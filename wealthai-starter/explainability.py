"""Explainability layer.

Deterministic templating over numbers already computed elsewhere in the
pipeline (optimizer, risk engine, goal simulator, tax estimator).
Deliberately not an LLM call: nothing here is a new estimate, and the
numbers it narrates are already final by the time this runs -- LLMs
interpret, they never invent the numbers themselves.
"""

from __future__ import annotations

import universe

_NAME_OF = {inst.ticker: inst.name for inst in universe.UNIVERSE}


def generate_explanation(
    client_name: str,
    effective_risk_score: float,
    risk_tolerance: float,
    risk_capacity: float,
    weights: dict[str, float],
    expected_annual_return: float,
    annual_volatility: float,
    sharpe_ratio: float,
    risk_metrics: dict[str, float],
    goal_result: dict | None = None,
    excluded_sectors: list[str] | None = None,
    tax_result: dict | None = None,
) -> str:
    top_holdings = sorted(weights.items(), key=lambda kv: -kv[1])[:3]
    top_str = ", ".join(
        f"{_NAME_OF.get(ticker, ticker)} ({weight:.0%})"
        for ticker, weight in top_holdings if weight > 0.001
    )

    lines = [
        f"{client_name}'s recommended portfolio is led by {top_str}, reflecting an "
        f"effective risk score of {effective_risk_score:.2f} "
        f"(tolerance {risk_tolerance:.2f}, capped by capacity {risk_capacity:.2f}).",
        f"Expected annual return {expected_annual_return:.1%} at {annual_volatility:.1%} "
        f"volatility (Sharpe {sharpe_ratio:.2f}).",
        f"Historical simulation puts max drawdown at {risk_metrics['max_drawdown']:.1%} "
        f"and 1-day 95% VaR at {risk_metrics['var_95_daily']:.1%} of portfolio value.",
    ]

    if tax_result is not None and tax_result["total_tax_drag"] > 0:
        lines.append(
            f"After an estimated {tax_result['total_tax_drag']:.1%} annual tax drag "
            f"({tax_result['jurisdiction_label']}), net expected return is "
            f"{tax_result['net_expected_return']:.1%}."
        )

    if goal_result is not None:
        lines.append(
            f"Monte Carlo simulation over {goal_result['years']:.0f} years estimates a "
            f"{goal_result['probability_of_success']:.0%} probability of reaching the "
            f"${goal_result['target_amount']:,.0f} goal (median outcome "
            f"${goal_result['median_outcome']:,.0f})."
        )

    if excluded_sectors:
        lines.append(f"Portfolio excludes: {', '.join(excluded_sectors)}, per client constraints.")

    return " ".join(lines)
