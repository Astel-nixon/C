"""Real market-data vendor integration.

Two free vendors, matched to what each is actually good for: Tiingo
for anything with a public ticker (equities, ETFs, bond funds, REITs,
commodity funds -- see universe.py's `real_ticker` field for the
mapping), Binance's public klines endpoint for crypto. Private equity,
private credit, and direct real estate have no `real_ticker` in
universe.py on purpose: nobody publishes a daily market price for
those, by definition -- they stay model-based regardless of
USE_REAL_DATA.

Originally built against CoinGecko for the crypto leg. Switched to
Binance after actually running this against live traffic: CoinGecko's
free tier no longer accepts unauthenticated requests (a 401 on the
very first real test, not a guess), while Binance's public kline
endpoint needs no key at all and was confirmed reachable. Tiingo's
side was verified the same way, same run. Binance paginates at 1000
candles per request, so a multi-year range needs more than one call --
handled below, not left as a future gap.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

import universe

EQUITY_BASE_URL = "https://api.tiingo.com/tiingo/daily"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_MAX_CANDLES = 1000
ONE_DAY_MS = 86_400_000

# Binance wants its own pair symbols, not universe.py's real_ticker strings.
BINANCE_SYMBOLS = {"btcusd": "BTCUSDT", "ethusd": "ETHUSDT"}


def _fetch_equity_like(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.Series:
    url = f"{EQUITY_BASE_URL}/{ticker}/prices"
    params = {"startDate": start_date, "endDate": end_date, "format": "json"}
    headers = {"Authorization": f"Token {api_key}"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.set_index("date")["adjClose"]


def _fetch_crypto(binance_ticker: str, start_date: str, end_date: str) -> pd.Series:
    symbol = BINANCE_SYMBOLS.get(binance_ticker)
    if symbol is None:
        raise ValueError(f"no Binance symbol mapped for {binance_ticker}")
    start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_date).timestamp() * 1000)

    rows = []
    cursor = start_ms
    while cursor < end_ms:
        resp = requests.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol, "interval": "1d", "startTime": cursor,
                    "endTime": end_ms, "limit": BINANCE_MAX_CANDLES},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open_time = batch[-1][0]
        if last_open_time < cursor:  # guards against a stalled cursor on a malformed response
            break
        cursor = last_open_time + ONE_DAY_MS

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base_volume", "taker_quote_volume", "ignore",
    ])
    df["date"] = pd.to_datetime(df["open_time"], unit="ms").dt.normalize()
    df["close"] = df["close"].astype(float)
    return df.drop_duplicates("date").set_index("date")["close"]


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
