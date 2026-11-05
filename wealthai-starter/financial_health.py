"""Pre-investment sanity checks a responsible advisor runs before ever
getting to portfolio construction: debt load and emergency liquidity.

Deterministic, rule-of-thumb guidance -- not a recommendation engine of
its own, and never an input to the optimizer, same boundary as every
other client-facing number in this project that isn't a real
quantitative model. Thresholds are standard financial-planning
conventions (the 3-6-month emergency fund guideline, treating total
debt above roughly half a year's income as worth flagging), not
derived from this specific client's situation -- labeled as such in
the copy itself, not quietly presented as more precise than it is.
"""

from __future__ import annotations


def debt_guidance(debt_to_income: float) -> dict:
    """debt_to_income is total debt / annual income, as defined on
    ClientProfile -- not the monthly-payment DTI ratio lenders use."""
    if debt_to_income >= 0.6:
        status = "high"
        note = (
            "Debt-to-income is high enough that most planners would suggest "
            "prioritizing high-interest debt paydown before investing "
            "aggressively -- a guaranteed debt payoff often beats an "
            "uncertain market return."
        )
    elif debt_to_income >= 0.3:
        status = "moderate"
        note = (
            "Debt-to-income is moderate. Common guidance is to keep paying "
            "down higher-interest debt alongside investing, rather than "
            "treating it as an either/or."
        )
    else:
        status = "low"
        note = "Debt-to-income is low enough that it isn't a factor holding back the plan below."
    return {"debt_to_income": round(debt_to_income, 2), "status": status, "note": note}


def emergency_fund_check(liquid_assets: float, annual_income: float) -> dict:
    """Months of income liquid_assets would cover, against the standard
    3-6-month emergency-fund guideline. annual_income stands in for
    monthly expenses, since this platform doesn't separately collect an
    expense figure -- an approximation, not a budget analysis."""
    if annual_income <= 0:
        return {
            "months_covered": None, "status": "unknown",
            "note": "No income entered, so emergency-fund coverage can't be estimated.",
        }

    months_covered = liquid_assets / (annual_income / 12)
    if months_covered < 3:
        status = "below"
        note = (
            f"Liquid assets cover about {months_covered:.1f} months of income -- "
            "below the commonly recommended 3-6 month emergency buffer. Worth "
            "keeping some portion of this outside the invested portfolio."
        )
    elif months_covered <= 6:
        status = "adequate"
        note = (
            f"Liquid assets cover about {months_covered:.1f} months of income -- "
            "within the commonly recommended 3-6 month range."
        )
    else:
        status = "above"
        note = (
            f"Liquid assets cover about {months_covered:.1f} months of income -- "
            "above the commonly recommended 3-6 month range, which may mean "
            "room to invest more of it."
        )
    return {"months_covered": round(months_covered, 1), "status": status, "note": note}
