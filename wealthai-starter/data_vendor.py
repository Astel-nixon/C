"""Real market-data vendor integration (Tiingo). WRITTEN, NOT VERIFIED.

Follows Tiingo's documented API shape (/tiingo/daily/{ticker}/prices for
equity-like instruments, /tiingo/crypto/prices for crypto) but has never
been executed against the live API in this environment -- no
TIINGO_API_KEY was available to test with. Before trusting this
anywhere downstream: get a free Tiingo key, run this file standalone,
and confirm the returned DataFrame's columns/shape match
synthetic_data.generate_synthetic_prices() (same asset columns, sane
price levels, no gaps after the ffill/dropna step).
"""

from __future__ import annotations

import os

import pandas as pd
import requests

EQUITY_BASE_URL = "https://api.tiingo.com/tiingo/daily"
CRYPTO_BASE_URL = "https://api.tiingo.com/tiingo/crypto/prices"

# Asset -> real ticker. Cash has no market price and is modeled separately.
EQUITY_LIKE_TICKERS = {
    "Global Equities": "VT",
    "Bonds": "BND",
    "Gold": "GLD",
    "REITs": "VNQ",
}
CRYPTO_TICKERS = {
    "Crypto": "btcusd",
}


def _fetch_equity_like(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.Series:
    url = f"{EQUITY_BASE_URL}/{ticker}/prices"
    params = {"startDate": start_date, "endDate": end_date, "format": "json"}
    headers = {"Authorization": f"Token {api_key}"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")["adjClose"]


def _fetch_crypto(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.Series:
    params = {
        "tickers": ticker,
        "startDate": start_date,
        "endDate": end_date,
        "resampleFreq": "1day",
    }
    headers = {"Authorization": f"Token {api_key}"}
    resp = requests.get(CRYPTO_BASE_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    price_data = resp.json()[0]["priceData"]
    df = pd.DataFrame(price_data)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")["close"]


def fetch_real_prices(start_date: str, end_date: str, api_key: str | None = None) -> pd.DataFrame:
    api_key = api_key or os.environ.get("TIINGO_API_KEY")
    if not api_key:
        raise RuntimeError("TIINGO_API_KEY not set (pass api_key= or set the env var)")

    series = {}
    for asset, ticker in EQUITY_LIKE_TICKERS.items():
        series[asset] = _fetch_equity_like(ticker, start_date, end_date, api_key)
    for asset, ticker in CRYPTO_TICKERS.items():
        series[asset] = _fetch_crypto(ticker, start_date, end_date, api_key)

    prices = pd.DataFrame(series).ffill().dropna()

    # Cash has no market price -- modeled as a stable instrument compounding
    # at a fixed assumed rate over the same date range as everything else.
    n = len(prices)
    daily_cash_return = 1.02 ** (1 / 252) - 1
    prices["Cash"] = 100.0 * (1 + daily_cash_return) ** pd.RangeIndex(n)

    return prices


if __name__ == "__main__":
    df = fetch_real_prices("2019-01-01", "2024-01-01")
    print(df.head())
    print(df.tail())
    print(f"\n{len(df)} rows fetched for columns: {list(df.columns)}")
