"""Tax-drag estimation.

Not a tax engine in the full sense (no lot-level cost basis, no real
tax-loss harvesting, no wash-sale rules) -- just enough to make the gap
between a portfolio's gross expected return and what an investor
actually keeps visible in a recommendation. Two components: tax on
income received along the way (dividends, coupons, interest -- from
each instrument's income_yield in universe.py) and tax on gains
actually realized through rebalancing turnover, at either the short- or
long-term rate depending on the client's assumed average holding
period.

Jurisdiction profiles below are illustrative approximations of real
regimes, not tax advice -- rates are simplified flat numbers standing
in for what are, in reality, bracketed and situation-dependent rules.
"""

from __future__ import annotations

from dataclasses import dataclass

import universe

INTEREST_LIKE_CLASSES = {"Bonds", "Cash"}
INTEREST_LIKE_TICKERS = {"PRIVATE_CREDIT"}  # asset_class is "Private Markets", taxed like interest


@dataclass(frozen=True)
class TaxProfile:
    name: str
    dividend_tax_rate: float
    interest_tax_rate: float
    short_term_gains_rate: float
    long_term_gains_rate: float
    long_term_threshold_years: float
    notes: str


JURISDICTIONS: dict[str, TaxProfile] = {
    "none": TaxProfile(
        "No tax modeled", 0.0, 0.0, 0.0, 0.0, 1.0,
        "Gross-of-tax baseline -- use for a tax-advantaged account or when tax simply isn't modeled.",
    ),
    "us_taxable": TaxProfile(
        "US, taxable brokerage account (illustrative)", 0.15, 0.32, 0.32, 0.15, 1.0,
        "Qualified-dividend and long-term capital gains rates at a mid-high bracket; "
        "interest and short-term gains at an illustrative ordinary-income rate.",
    ),
    "uk": TaxProfile(
        "UK, general investment account (illustrative)", 0.339, 0.40, 0.20, 0.20, 1.0,
        "Simplified higher-rate dividend and income tax; UK capital gains tax doesn't "
        "distinguish short/long term the way the US does, so both rates are set equal here.",
    ),
    "singapore": TaxProfile(
        "Singapore, individual investor", 0.0, 0.0, 0.0, 0.0, 1.0,
        "Singapore doesn't tax capital gains or most investment income for individuals -- "
        "functionally identical to the 'none' baseline, kept separate for clarity in reports.",
    ),
    "india": TaxProfile(
        "India, individual investor (illustrative)", 0.30, 0.30, 0.20, 0.125, 1.0,
        "Simplified: dividends and interest at an illustrative top slab rate; equity-style "
        "long-term gains at the concessional rate, short-term at the higher slab-linked rate.",
    ),
}


def _income_tax_rate_for(ticker: str, asset_class: str, profile: TaxProfile) -> float:
    if asset_class in INTEREST_LIKE_CLASSES or ticker in INTEREST_LIKE_TICKERS:
        return profile.interest_tax_rate
    return profile.dividend_tax_rate


def estimate_after_tax_return(
    weights: dict[str, float],
    gross_expected_return: float,
    jurisdiction: str = "none",
    annual_turnover: float = 0.20,
    avg_holding_period_years: float = 2.0,
) -> dict:
    profile = JURISDICTIONS.get(jurisdiction, JURISDICTIONS["none"])

    income_yield = sum(w * universe.INCOME_YIELD_OF.get(t, 0.0) for t, w in weights.items())
    income_tax_drag = sum(
        w * universe.INCOME_YIELD_OF.get(t, 0.0)
        * _income_tax_rate_for(t, universe.ASSET_CLASS_OF.get(t, ""), profile)
        for t, w in weights.items()
    )

    capital_gains_rate = (
        profile.long_term_gains_rate
        if avg_holding_period_years >= profile.long_term_threshold_years
        else profile.short_term_gains_rate
    )
    price_appreciation = max(gross_expected_return - income_yield, 0.0)
    realized_gains_drag = price_appreciation * annual_turnover * capital_gains_rate

    total_drag = income_tax_drag + realized_gains_drag
    net_expected_return = gross_expected_return - total_drag

    return {
        "jurisdiction": jurisdiction,
        "jurisdiction_label": profile.name,
        "gross_expected_return": round(gross_expected_return, 5),
        "income_yield": round(income_yield, 5),
        "income_tax_drag": round(income_tax_drag, 5),
        "realized_gains_drag": round(realized_gains_drag, 5),
        "total_tax_drag": round(total_drag, 5),
        "net_expected_return": round(net_expected_return, 5),
        "notes": profile.notes,
    }
