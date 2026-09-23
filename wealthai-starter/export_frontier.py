"""Standalone interactive frontier demo (CLAUDE.md Section 3).

Precomputes portfolio weights/return/volatility across a fine grid of
risk-tolerance values in Python -- the only place PyPortfolioOpt runs --
then embeds that grid as JSON into a single self-contained HTML file.
The browser side is just a slider indexing into the precomputed grid:
no server, no client-side optimization, works from a local file:// URL.
"""

from __future__ import annotations

import json
from pathlib import Path

from portfolio_optimizer import optimize_portfolio
from synthetic_data import ASSET_NAMES, generate_synthetic_prices

RISK_STEPS = 41  # 0.00, 0.025, ..., 1.00
OUTPUT_FILE = Path(__file__).parent / "wealth_demo.html"


def build_grid(prices, crypto_cap: float = 0.05, min_cash: float = 0.05) -> list[dict]:
    grid = []
    for i in range(RISK_STEPS):
        risk_tolerance = round(i / (RISK_STEPS - 1), 4)
        result = optimize_portfolio(
            prices,
            risk_tolerance=risk_tolerance,
            crypto_cap=crypto_cap,
            min_cash=min_cash,
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


def render_html(grid: list[dict], asset_names: list[str]) -> str:
    template = (Path(__file__).parent / "wealth_demo_template.html").read_text()
    return template.replace("__GRID_JSON__", json.dumps(grid)).replace(
        "__ASSETS_JSON__", json.dumps(asset_names)
    )


def main() -> None:
    prices = generate_synthetic_prices(years=5, seed=42)
    grid = build_grid(prices)
    html = render_html(grid, list(prices.columns))
    OUTPUT_FILE.write_text(html)
    print(f"Wrote {OUTPUT_FILE} with {len(grid)} precomputed grid points.")


if __name__ == "__main__":
    main()
