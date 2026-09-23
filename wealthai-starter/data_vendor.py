"""Real market-data vendor integration. WRITTEN, NOT VERIFIED.

Two free vendors, matched to what each is actually good for:
Tiingo for anything with a public ticker (equities, ETFs, bond funds,
REITs, commodity funds -- see universe.py's `real_ticker` field for the
mapping), CoinGecko for crypto, since it needs no signup at all for the
basic price endpoints. Private equity, private credit, and direct real
estate have no `real_ticker` in universe.py on purpose: nobody publishes
a daily market price for those, by definition -- they stay model-based
regardless of USE_REAL_DATA.

Never executed against either live API in this environment -- no
TIINGO_API_KEY was available, and this sandbox's egress policy blocks
outbound connections to every external data host it was tested against,
CoinGecko included. Before trusting this anywhere: get a free Tiingo
key, run this file standalone somewhere with real network access, and
confirm the returned DataFrame's columns/shape match
universe.generate_universe_prices() (same tickers, no gaps after the
ffill/dropna step).
"""

from __future__ import annotations

import os

import pandas as pd
import requests

import universe

EQUITY_BASE_URL = "https://api.tiingo.com/tiingo/daily"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# CoinGecko's free "coins/{id}/market_chart/range" endpoint wants its own
# coin ids, not ticker symbols -- mapped from universe.py's real_ticker.
COINGECKO_IDS = {"btcusd": "bitcoin", "ethusd": "ethereum"}


def _fetch_equity_like(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.Series:
    url = f"{EQUITY_BASE_URL}/{ticker}/prices"
    params = {"startDate": start_date, "endDate": end_date, "format": "json"}
    headers = {"Authorization": f"Token {api_key}"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")["adjClose"]


def _fetch_crypto(coingecko_ticker: str, start_date: str, end_date: str) -> pd.Series:
    coin_id = COINGECKO_IDS.get(coingecko_ticker)
    if coin_id is None:
        raise ValueError(f"no CoinGecko id mapped for {coingecko_ticker}")
    from_ts = int(pd.Timestamp(start_date).timestamp())
    to_ts = int(pd.Timestamp(end_date).timestamp())
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart/range"
    resp = requests.get(url, params={"vs_currency": "usd", "from": from_ts, "to": to_ts}, timeout=30)
    resp.raise_for_status()
    prices = resp.json()["prices"]  # list of [ms_timestamp, price]
    df = pd.DataFrame(prices, columns=["ts", "price"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
    return df.groupby("date")["price"].last()


def fetch_real_prices(start_date: str, end_date: str, api_key: str | None = None) -> pd.DataFrame:
    api_key = api_key or os.environ.get("TIINGO_API_KEY")
    if not api_key:
        raise RuntimeError("TIINGO_API_KEY not set (pass api_key= or set the env var)")

    series: dict[str, pd.Series] = {}
    for inst in universe.UNIVERSE:
        if inst.real_ticker is None or inst.asset_class == "Crypto":
            continue
        series[inst.ticker] = _fetch_equity_like(inst.real_ticker, start_date, end_date, api_key)

    for inst in universe.UNIVERSE:
        if inst.asset_class == "Crypto" and inst.real_ticker:
            series[inst.ticker] = _fetch_crypto(inst.real_ticker, start_date, end_date)

    prices = pd.DataFrame(series).ffill().dropna()

    # Everything without a real_ticker (private markets, direct real estate,
    # cash) has no market price to fetch -- fall back to their synthetic
    # generator so the returned frame still has every universe column.
    missing = [inst for inst in universe.UNIVERSE if inst.ticker not in prices.columns]
    if missing:
        years = max((len(prices) if len(prices) else 252 * 5) / 252, 1.0)
        synthetic = universe.generate_universe_prices(years=years, seed=42)
        synthetic = synthetic.reindex(prices.index, method="nearest")
        for inst in missing:
            prices[inst.ticker] = synthetic[inst.ticker]

    return prices[universe.TICKERS]


if __name__ == "__main__":
    df = fetch_real_prices("2019-01-01", "2024-01-01")
    print(df.head())
    print(df.tail())
    print(f"\n{len(df)} rows fetched for columns: {list(df.columns)}")
