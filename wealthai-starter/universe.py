"""The investable universe: what instruments exist, and how their returns
are related to each other.

Two things live here that used to be conflated in synthetic_data.py's
flat six-bucket list: instrument metadata (asset class, region, sector
tags for exclusion screening, liquidity tier) and the return-generation
model itself.

Instead of hand-tuning a 25x25 correlation matrix directly (unreliable
past a handful of assets -- easy to make an inconsistent, non-positive-
-semidefinite matrix by accident), returns are generated from a small
statistical factor model: six latent factors (Equity, Rates, Credit,
Commodity, Crypto, RealAsset) with a hand-specified but eigenvalue-
checked correlation structure, each instrument expressed as a set of
loadings onto those factors plus its own idiosyncratic noise. This is
the same basic construction real risk systems use (Barra-style factor
models, just much smaller), and it guarantees a valid covariance matrix
by construction: Sigma = B @ R_F @ B.T + D, sum of a PSD term and a
diagonal (also PSD) term.

Private equity, private credit, and direct real estate get an
additional AR(1) smoothing pass on top of their factor-model returns --
real appraisal-based valuations move less than their true economic risk
because they're marked infrequently and by appraisal rather than
continuous trading (the standard reference is Geltner's unsmoothing
literature). Modeling them with an already-low target volatility would
hide that this is a smoothing artifact, not genuinely lower risk;
applying the smoothing filter explicitly keeps that distinction visible
in the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

FACTORS = ["Equity", "Rates", "Credit", "Commodity", "Crypto", "RealAsset"]

_FACTOR_CORR_PAIRS = {
    ("Equity", "Rates"): -0.20, ("Equity", "Credit"): 0.50, ("Equity", "Commodity"): 0.15,
    ("Equity", "Crypto"): 0.35, ("Equity", "RealAsset"): 0.40,
    ("Rates", "Credit"): 0.30, ("Rates", "Commodity"): -0.10, ("Rates", "Crypto"): -0.05,
    ("Rates", "RealAsset"): -0.15,
    ("Credit", "Commodity"): 0.05, ("Credit", "Crypto"): 0.10, ("Credit", "RealAsset"): 0.20,
    ("Commodity", "Crypto"): 0.20, ("Commodity", "RealAsset"): 0.25,
    ("Crypto", "RealAsset"): 0.10,
}


def _build_factor_correlation() -> np.ndarray:
    n = len(FACTORS)
    idx = {f: i for i, f in enumerate(FACTORS)}
    corr = np.eye(n)
    for (a, b), value in _FACTOR_CORR_PAIRS.items():
        corr[idx[a], idx[b]] = value
        corr[idx[b], idx[a]] = value
    eigvals = np.linalg.eigvalsh(corr)
    if eigvals.min() < -1e-8:
        raise ValueError(f"factor correlation matrix is not PSD (min eigenvalue {eigvals.min()})")
    return corr


FACTOR_CORRELATION = _build_factor_correlation()


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    asset_class: str  # broad bucket used for stress shocks and group caps
    region: str
    sector_tags: tuple[str, ...]  # e.g. ("fossil_fuels",) -- matched against client exclusions
    liquidity_tier: str  # "liquid" or "illiquid"
    target_return: float  # annualized
    target_vol: float  # annualized
    factor_loadings: dict[str, float] = field(default_factory=dict)  # vol units per factor
    real_ticker: str | None = None  # vendor symbol, when a public one exists
    smoothing_theta: float = 0.0  # AR(1) coefficient; 0 = no smoothing (liquid, marked to market)
    income_yield: float = 0.0  # annual dividend/coupon/distribution yield, part of target_return


UNIVERSE: list[Instrument] = [
    # -- Equities --
    Instrument("US_EQUITY", "US Total Market Equity", "Equity", "US", (), "liquid",
               0.09, 0.16, {"Equity": 0.155}, real_ticker="VTI", income_yield=0.015),
    Instrument("INTL_EQUITY", "International Developed Equity", "Equity", "Intl", (), "liquid",
               0.075, 0.17, {"Equity": 0.15, "Rates": 0.03}, real_ticker="VEA", income_yield=0.028),
    Instrument("EM_EQUITY", "Emerging Markets Equity", "Equity", "EM", (), "liquid",
               0.085, 0.22, {"Equity": 0.17, "Commodity": 0.05, "Credit": 0.04}, real_ticker="VWO",
               income_yield=0.026),
    Instrument("ENERGY_EQUITY", "Energy Sector Equity", "Equity", "US", ("fossil_fuels",), "liquid",
               0.08, 0.28, {"Equity": 0.16, "Commodity": 0.18}, real_ticker="XLE", income_yield=0.032),
    Instrument("DEFENSE_EQUITY", "Aerospace & Defense Equity", "Equity", "US", ("weapons",), "liquid",
               0.10, 0.20, {"Equity": 0.185}, real_ticker="ITA", income_yield=0.012),
    Instrument("TOBACCO_EQUITY", "Tobacco Sector Equity", "Equity", "US", ("tobacco",), "liquid",
               0.07, 0.19, {"Equity": 0.15, "Credit": 0.03}, real_ticker="VDC", income_yield=0.041),
    Instrument("CLEAN_ENERGY_EQUITY", "Clean Energy Equity", "Equity", "Global", ("renewable",),
               "liquid", 0.095, 0.30, {"Equity": 0.19, "Commodity": -0.05}, real_ticker="ICLN",
               income_yield=0.008),
    Instrument("CASINO_EQUITY", "Gaming & Casino Equity", "Equity", "US", ("gambling",), "liquid",
               0.09, 0.26, {"Equity": 0.18, "Credit": 0.05}, real_ticker="BJK", income_yield=0.014),

    # -- Fixed income --
    Instrument("GOVT_BONDS", "US Treasury Bonds", "Bonds", "US", (), "liquid",
               0.03, 0.05, {"Rates": 0.05}, real_ticker="GOVT", income_yield=0.035),
    Instrument("CORP_BONDS", "US Corporate Bonds", "Bonds", "US", (), "liquid",
               0.045, 0.08, {"Rates": 0.055, "Credit": 0.045}, real_ticker="LQD", income_yield=0.048),
    Instrument("INTL_BONDS", "International Government Bonds", "Bonds", "Intl", (), "liquid",
               0.025, 0.07, {"Rates": 0.045, "Equity": 0.02}, real_ticker="BNDX", income_yield=0.030),
    Instrument("TIPS", "Treasury Inflation-Protected Securities", "Bonds", "US", (), "liquid",
               0.025, 0.06, {"Rates": 0.045, "Commodity": 0.02}, real_ticker="TIP", income_yield=0.020),

    # -- Commodities --
    Instrument("GOLD", "Gold", "Commodities", "Global", (), "liquid",
               0.04, 0.15, {"Commodity": 0.14}, real_ticker="GLD"),
    Instrument("SILVER", "Silver", "Commodities", "Global", (), "liquid",
               0.035, 0.27, {"Commodity": 0.24, "Equity": 0.05}, real_ticker="SLV"),
    Instrument("BROAD_COMMODITIES", "Broad Commodities Basket", "Commodities", "Global",
               ("fossil_fuels",), "liquid", 0.03, 0.18, {"Commodity": 0.17}, real_ticker="DBC"),

    # -- Real assets --
    Instrument("REITS", "Publicly Traded REITs", "Real Estate", "US", (), "liquid",
               0.06, 0.18, {"Equity": 0.10, "RealAsset": 0.13}, real_ticker="VNQ", income_yield=0.038),
    Instrument("DIRECT_REAL_ESTATE", "Direct Real Estate (unlisted)", "Real Estate", "US", (),
               "illiquid", 0.065, 0.11, {"RealAsset": 0.10, "Rates": -0.02}, smoothing_theta=0.65,
               income_yield=0.040),

    # -- Private markets --
    Instrument("PRIVATE_EQUITY", "Private Equity", "Private Markets", "Global", (), "illiquid",
               0.11, 0.14, {"Equity": 0.13, "Credit": 0.04}, smoothing_theta=0.70),
    Instrument("PRIVATE_CREDIT", "Private Credit / Direct Lending", "Private Markets", "Global",
               (), "illiquid", 0.075, 0.08, {"Credit": 0.07, "Rates": 0.02}, smoothing_theta=0.60,
               income_yield=0.065),

    # -- Crypto --
    Instrument("BITCOIN", "Bitcoin", "Crypto", "Global", (), "liquid",
               0.22, 0.65, {"Crypto": 0.62}, real_ticker="btcusd"),
    Instrument("ETHEREUM", "Ethereum", "Crypto", "Global", (), "liquid",
               0.24, 0.75, {"Crypto": 0.68, "Equity": 0.08}, real_ticker="ethusd"),

    # -- Cash --
    Instrument("CASH", "Cash / Money Market", "Cash", "US", (), "liquid", 0.02, 0.005, {},
               income_yield=0.02),
]

TICKERS = [inst.ticker for inst in UNIVERSE]
ASSET_CLASS_OF = {inst.ticker: inst.asset_class for inst in UNIVERSE}
SECTOR_TAGS_OF = {inst.ticker: set(inst.sector_tags) for inst in UNIVERSE}
LIQUIDITY_OF = {inst.ticker: inst.liquidity_tier for inst in UNIVERSE}
INCOME_YIELD_OF = {inst.ticker: inst.income_yield for inst in UNIVERSE}


def tickers_matching_sectors(excluded_sectors: list[str]) -> set[str]:
    """Which instruments carry any of the client's excluded sector tags."""
    excluded = set(excluded_sectors)
    return {t for t, tags in SECTOR_TAGS_OF.items() if tags & excluded}


def illiquid_tickers() -> set[str]:
    return {t for t, tier in LIQUIDITY_OF.items() if tier == "illiquid"}


def _apply_smoothing(returns: np.ndarray, theta: float) -> np.ndarray:
    """AR(1) appraisal smoothing: observed_t = theta*observed_{t-1} + (1-theta)*true_t."""
    if theta <= 0:
        return returns
    smoothed = np.empty_like(returns)
    smoothed[0] = returns[0]
    for t in range(1, len(returns)):
        smoothed[t] = theta * smoothed[t - 1] + (1 - theta) * returns[t]
    return smoothed


def generate_universe_prices(
    years: float = 5.0, start_price: float = 100.0, seed: int | None = 42
) -> pd.DataFrame:
    n_days = int(round(years * TRADING_DAYS_PER_YEAR))
    rng = np.random.default_rng(seed)

    factor_daily_returns = rng.multivariate_normal(
        mean=np.zeros(len(FACTORS)),
        cov=FACTOR_CORRELATION / TRADING_DAYS_PER_YEAR,
        size=n_days,
    )
    factor_idx = {f: i for i, f in enumerate(FACTORS)}

    columns = {}
    for inst in UNIVERSE:
        daily_mean = (1 + inst.target_return) ** (1 / TRADING_DAYS_PER_YEAR) - 1

        factor_var = sum(
            inst.factor_loadings.get(fa, 0.0) * inst.factor_loadings.get(fb, 0.0)
            * FACTOR_CORRELATION[factor_idx[fa], factor_idx[fb]]
            for fa in inst.factor_loadings for fb in inst.factor_loadings
        )
        idio_var = max(inst.target_vol ** 2 - factor_var, (inst.target_vol * 0.15) ** 2)
        idio_daily_std = np.sqrt(idio_var / TRADING_DAYS_PER_YEAR)

        factor_component = np.zeros(n_days)
        for factor_name, loading in inst.factor_loadings.items():
            factor_component += loading * factor_daily_returns[:, factor_idx[factor_name]]

        idio_component = rng.normal(0, idio_daily_std, size=n_days)
        daily_returns = daily_mean + factor_component + idio_component

        if inst.smoothing_theta > 0:
            daily_returns = _apply_smoothing(daily_returns, inst.smoothing_theta)

        columns[inst.ticker] = start_price * np.cumprod(1 + daily_returns)

    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=n_days)
    return pd.DataFrame(columns, index=dates)


if __name__ == "__main__":
    prices = generate_universe_prices()
    print(f"{len(UNIVERSE)} instruments, {len(prices)} trading days")
    realized_vol = prices.pct_change().std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    for inst in UNIVERSE:
        print(f"  {inst.ticker:<22} target_vol={inst.target_vol:.2%}  realized_vol={realized_vol[inst.ticker]:.2%}")
