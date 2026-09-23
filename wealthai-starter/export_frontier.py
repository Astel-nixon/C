"""Standalone interactive frontier demo.

Precomputes portfolio weights/return/volatility across a fine grid of
risk-tolerance values in Python -- the only place PyPortfolioOpt runs --
then embeds that grid as JSON into a single self-contained HTML file.
The browser side is just a slider indexing into the precomputed grid:
no server, no client-side optimization, works from a local file:// URL.
"""

from __future__ import annotations

import json
from pathlib import Path

import universe
from house_view import prior_returns_series
from portfolio_optimizer import Constraints, optimize_portfolio

RISK_STEPS = 41  # 0.00, 0.025, ..., 1.00
OUTPUT_FILE = Path(__file__).parent / "wealth_demo.html"


def build_grid(prices, crypto_cap: float = 0.08, illiquid_cap: float = 0.25, min_cash: float = 0.05) -> list[dict]:
    constraints = Constraints(
        min_cash=min_cash,
        cash_ticker="CASH",
        group_caps={"Crypto": crypto_cap, "Illiquid": illiquid_cap},
        groups={
            "Crypto": {t for t, c in universe.ASSET_CLASS_OF.items() if c == "Crypto"},
            "Illiquid": universe.illiquid_tickers(),
        },
    )
    prior = prior_returns_series()

    grid = []
    for i in range(RISK_STEPS):
        risk_tolerance = round(i / (RISK_STEPS - 1), 4)
        result = optimize_portfolio(
            prices,
            risk_tolerance=risk_tolerance,
            constraints=constraints,
            expected_returns_prior=prior,
            n_frontier_points=0,
        )
        grid.append(
            {
                "risk_tolerance": risk_tolerance,
                "weights": result.weights,
                "expected_return": result.expected_annual_return,
                "volatility": result.annual_volatility,
                "sharpe": result.sharpe_ratio,
            }
        )
    return grid


def render_html(grid: list[dict]) -> str:
    template = (Path(__file__).parent / "wealth_demo_template.html").read_text()
    names = {inst.ticker: inst.name for inst in universe.UNIVERSE}
    classes = {inst.ticker: inst.asset_class for inst in universe.UNIVERSE}
    return (
        template.replace("__GRID_JSON__", json.dumps(grid))
        .replace("__NAMES_JSON__", json.dumps(names))
        .replace("__CLASSES_JSON__", json.dumps(classes))
    )


def main() -> None:
    prices = universe.generate_universe_prices(years=5, seed=42)
    grid = build_grid(prices)
    html = render_html(grid)
    OUTPUT_FILE.write_text(html)
    print(f"Wrote {OUTPUT_FILE} with {len(grid)} precomputed grid points across {len(universe.UNIVERSE)} instruments.")


if __name__ == "__main__":
    main()
