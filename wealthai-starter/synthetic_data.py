"""Placeholder multi-asset price generator.

Stands in for a real data vendor (see Part B §2.4 of the master plan) until
API access is wired up. Every downstream module only consumes a DataFrame
of prices and does not care where they came from, so swapping this out for
Financial Modeling Prep / Tiingo / FRED / CoinGecko later is a drop-in
replacement, not a rewrite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ASSET_NAMES = ["Global Equities", "Bonds", "Gold", "REITs", "Crypto", "Cash"]

# Long-run annualized return/volatility assumptions per asset class.
ANNUAL_RETURN = {
    "Global Equities": 0.08,
    "Bonds": 0.03,
    "Gold": 0.04,
    "REITs": 0.06,
    "Crypto": 0.20,
    "Cash": 0.02,
}

ANNUAL_VOL = {
    "Global Equities": 0.16,
    "Bonds": 0.05,
    "Gold": 0.15,
    "REITs": 0.18,
    "Crypto": 0.70,
    "Cash": 0.005,
}

# Plausible cross-asset correlation matrix, ordered per ASSET_NAMES.
CORRELATION = pd.DataFrame(
    [
        [1.00, -0.10, 0.00, 0.60, 0.35, 0.00],
        [-0.10, 1.00, 0.10, -0.05, -0.05, 0.05],
        [0.00, 0.10, 1.00, 0.10, 0.15, 0.00],
        [0.60, -0.05, 0.10, 1.00, 0.25, 0.00],
        [0.35, -0.05, 0.15, 0.25, 1.00, 0.00],
        [0.00, 0.05, 0.00, 0.00, 0.00, 1.00],
    ],
    index=ASSET_NAMES,
    columns=ASSET_NAMES,
)

TRADING_DAYS_PER_YEAR = 252


def generate_synthetic_prices(
    years: float = 5.0,
    start_price: float = 100.0,
    seed: int | None = 42,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Generate correlated daily price series for the fixed asset universe.

    Daily returns are drawn from a multivariate normal distribution whose
    per-asset mean/vol and cross-asset correlation are calibrated to the
    long-run assumptions above, then compounded into a price level series.
    """
    n_days = int(round(years * TRADING_DAYS_PER_YEAR))
    rng = np.random.default_rng(seed)

    daily_mean = np.array(
        [(1 + ANNUAL_RETURN[a]) ** (1 / TRADING_DAYS_PER_YEAR) - 1 for a in ASSET_NAMES]
    )
    daily_vol = np.array([ANNUAL_VOL[a] / np.sqrt(TRADING_DAYS_PER_YEAR) for a in ASSET_NAMES])

    corr = CORRELATION.loc[ASSET_NAMES, ASSET_NAMES].to_numpy()
    cov = np.outer(daily_vol, daily_vol) * corr

    daily_returns = rng.multivariate_normal(mean=daily_mean, cov=cov, size=n_days)

    if end_date is not None:
        end = pd.Timestamp(end_date)
    else:
        end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=n_days)

    prices = start_price * np.cumprod(1 + daily_returns, axis=0)
    return pd.DataFrame(prices, index=dates, columns=ASSET_NAMES)


if __name__ == "__main__":
    df = generate_synthetic_prices()
    print(df.head())
    print("...")
    print(df.tail())
    print(f"\n{len(df)} trading days generated for {len(ASSET_NAMES)} assets.")
