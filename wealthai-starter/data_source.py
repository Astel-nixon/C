"""Data source switch (CLAUDE.md Step 1).

Single place that decides synthetic vs. real prices, so main.py and
api.py don't each need their own USE_REAL_DATA branching. Defaults to
synthetic -- real data requires TIINGO_API_KEY and outbound network
access to api.tiingo.com, neither of which this sandbox has (see
data_vendor.py's module docstring). Flipping USE_REAL_DATA=1 outside
this sandbox is untested; if it breaks, that's exactly what Step 1 in
CLAUDE.md asks someone to go verify.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd

import synthetic_data


def get_prices(years: float = 5.0, seed: int | None = 42) -> pd.DataFrame:
    """Returns a prices DataFrame plus a data_version tag for the audit log."""
    if os.environ.get("USE_REAL_DATA") == "1":
        import data_vendor  # imported lazily: pulls in `requests`, only needed here

        end = date.today()
        start = end - timedelta(days=int(years * 365.25))
        prices = data_vendor.fetch_real_prices(start.isoformat(), end.isoformat())
        return prices, f"tiingo:{start.isoformat()}:{end.isoformat()}"

    prices = synthetic_data.generate_synthetic_prices(years=years, seed=seed)
    return prices, f"synthetic:years={years}:seed={seed}"
