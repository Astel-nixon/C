"""Scenario stress testing (master plan Part A §18).

Five illustrative macro scenarios applied to the client's actual chosen
weights. Shock magnitudes are illustrative placeholders, not yet
calibrated to historical analogues (GFC, COVID, specific rate cycles --
see master plan Part B §4 gap #9/#10 equivalent). Each scenario shocks
only the assets it lists; unlisted assets are held flat for that
scenario, which is a simplification worth revisiting once the universe
moves beyond broad asset classes (master plan Step 4).
"""

from __future__ import annotations

SCENARIOS: dict[str, dict[str, float]] = {
    "Equity Crash (-40%)": {"Global Equities": -0.40, "REITs": -0.30, "Crypto": -0.55},
    "Rate Shock (+300bps)": {"Bonds": -0.15, "REITs": -0.12, "Global Equities": -0.10},
    "Inflation Shock": {"Bonds": -0.10, "Cash": -0.06, "Gold": 0.15, "Global Equities": -0.08},
    "Recession": {"Global Equities": -0.30, "REITs": -0.25, "Crypto": -0.50, "Bonds": 0.05},
    "Crypto Crash (-70%)": {"Crypto": -0.70},
}


def run_stress_tests(weights: dict[str, float]) -> dict[str, float]:
    """Portfolio-level P&L impact (as a fraction) under each named scenario."""
    results = {}
    for scenario_name, shocks in SCENARIOS.items():
        impact = sum(weights.get(asset, 0.0) * shock for asset, shock in shocks.items())
        results[scenario_name] = round(impact, 4)
    return results
