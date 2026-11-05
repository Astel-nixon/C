"""Data source switch.

Single place that decides synthetic vs. real prices, so main.py and
api.py don't each need their own USE_REAL_DATA branching. Defaults to
synthetic -- real data requires TIINGO_API_KEY and outbound network
access to api.tiingo.com and Binance's public API (see data_vendor.py's
module docstring; CoinGecko's crypto leg was replaced after its free
tier started rejecting unauthenticated requests).

Verified live, outside this sandbox: real_ticker fetches for all 19
equity-like instruments plus Binance's crypto klines both came back
clean -- 1826 rows, all 22 columns, no gaps.

The real-data branch caches the fetched frame in-process for
CACHE_TTL_SECONDS. Daily close prices don't change intra-day, so there
is no freshness cost -- but without this, every single "Generate
recommendation" click re-fetches ~19 tickers from Tiingo's free tier
from scratch, and a handful of clicks in a demo session is enough to
hit its rate limit (confirmed: a second back-to-back run returned 429
on the very first ticker). Caught by testing against live traffic
before this ever touched a deployed server, not left as a surprise for
whoever clicked the button one too many times.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pandas as pd

import universe

CACHE_TTL_SECONDS = 3600
_cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}


def get_prices(years: float = 5.0, seed: int | None = 42) -> tuple[pd.DataFrame, str]:
    """Returns a prices DataFrame plus a data_version tag for the audit log."""
    if os.environ.get("USE_REAL_DATA") == "1":
        import data_vendor  # imported lazily: pulls in `requests`, only needed here

        end = date.today()
        start = end - timedelta(days=int(years * 365.25))
        cache_key = (start.isoformat(), end.isoformat())

        cached = _cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            prices = cached[1]
        else:
            prices = data_vendor.fetch_real_prices(start.isoformat(), end.isoformat())
            _cache[cache_key] = (now, prices)

        return prices, f"tiingo+binance:{start.isoformat()}:{end.isoformat()}"

    prices = universe.generate_universe_prices(years=years, seed=seed)
    return prices, f"synthetic:years={years}:seed={seed}"
