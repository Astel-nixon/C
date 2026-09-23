"""Scenario stress testing.

Shocks are defined per asset class (Equity, Bonds, Commodities, Real
Estate, Private Markets, Crypto, Cash) and applied through
universe.ASSET_CLASS_OF, rather than naming individual tickers -- with
22 instruments in the universe, a shock table keyed by ticker would be
both unreadable and wrong the moment a new instrument gets added.
Magnitudes are illustrative, not calibrated to specific historical
analogues (GFC, COVID, particular rate cycles) yet -- that calibration
is worth doing once there's a real benchmark to check them against.
"""

from __future__ import annotations

import universe

SCENARIOS: dict[str, dict[str, float]] = {
    "Equity Crash (-40%)": {
        "Equity": -0.40, "Real Estate": -0.28, "Private Markets": -0.20, "Crypto": -0.55,
    },
    "Rate Shock (+300bps)": {
        "Bonds": -0.15, "Real Estate": -0.12, "Equity": -0.10, "Private Markets": -0.05,
    },
    "Inflation Shock": {
        "Bonds": -0.10, "Cash": -0.06, "Commodities": 0.18, "Equity": -0.08,
    },
    "Recession": {
        "Equity": -0.30, "Real Estate": -0.22, "Private Markets": -0.18, "Crypto": -0.50,
        "Bonds": 0.05,
    },
    "Crypto Crash (-70%)": {
        "Crypto": -0.70,
    },
    "Liquidity Crunch": {
        # Illiquid marks get hit hardest when forced to sell into a thin
        # market -- distinct from Equity Crash, which is a public-market
        # repricing shock, not a liquidity event.
        "Private Markets": -0.35, "Real Estate": -0.15, "Equity": -0.15, "Crypto": -0.30,
    },
}


def run_stress_tests(weights: dict[str, float]) -> dict[str, float]:
    """Portfolio-level P&L impact (as a fraction) under each named scenario."""
    results = {}
    for scenario_name, class_shocks in SCENARIOS.items():
        impact = sum(
            weight * class_shocks.get(universe.ASSET_CLASS_OF.get(ticker, ""), 0.0)
            for ticker, weight in weights.items()
        )
        results[scenario_name] = round(impact, 4)
    return results
