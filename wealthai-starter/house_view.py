"""Capital market assumptions: the shrinkage prior for estimators.py.

Every major wealth manager publishes something like this table once a
year -- a plain, asset-class-level view of "what's a reasonable
long-run return to expect here," usually built from a mix of valuation
models, historical risk premia, and judgment. It's deliberately coarse
(one number per asset class, not per instrument) and deliberately not
derived from this project's own synthetic data generator -- if it were,
shrinking toward it would just be recovering the answer key rather than
doing real estimation work. In production this table is exactly what
should get replaced with an actual house view, reviewed and revised on
a cadence, not left as engineering-team guesses.
"""

from __future__ import annotations

import pandas as pd

import universe

PRIOR_RETURN_BY_CLASS: dict[str, float] = {
    "Equity": 0.065,
    "Bonds": 0.035,
    "Commodities": 0.03,
    "Real Estate": 0.05,
    "Private Markets": 0.06,
    "Crypto": 0.10,
    "Cash": 0.02,
}


def prior_returns_series() -> pd.Series:
    return pd.Series({
        inst.ticker: PRIOR_RETURN_BY_CLASS.get(inst.asset_class, 0.04) for inst in universe.UNIVERSE
    })
