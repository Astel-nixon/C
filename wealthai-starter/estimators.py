"""Expected-return estimation.

Plain historical sample means get noisy fast: with a 20+ instrument
universe, even two decades of daily data isn't enough to reliably tell
apart two assets' true expected returns from the noise in their price
paths -- this is a well-known result in the literature (see Merton
1980 on the difficulty of estimating drift from price data), not a
quirk of this particular dataset. Feeding raw sample means into an
optimizer means whichever asset had the luckiest draw looks best, and
the optimizer -- correctly, given what it was told -- piles into it.

This shrinks each asset's sample mean toward a *prior*, not toward the
noisy cross-sectional average of the sample itself (plain James-Stein
does the latter, and inherits some of the same noise it's trying to
correct for). The prior defaults to the cross-sectional grand mean if
none is supplied, but the real intended use is to pass in an external
view -- a set of capital market assumptions, the kind every major
wealth manager publishes annually -- so shrinkage pulls estimates
toward an independent view of what's reasonable, not just toward
whatever this particular sample happened to average out to. That's the
same idea Black-Litterman is built on (blend a market/house prior with
data-implied views); this is the lightweight version of it, without
the full equilibrium-return machinery.

Shrinkage intensity (how much weight the prior gets vs. the sample) is
set by the classic Efron-Morris / James-Stein rule: the ratio of
estimation-error variance to how far the sample means actually sit from
the prior. When that dispersion is small relative to the noise (the
common case here), shrinkage saturates and the estimate collapses
toward the prior -- a deliberately humble response to a genuinely hard
estimation problem, not a bug.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# See the module docstring: full (100%) shrinkage would make every
# asset's expected return identical to the prior, which makes "highest
# return portfolio" undefined (every feasible allocation ties). Capping
# below 1.0 keeps the frontier well-posed while still being aggressive
# regularization -- this cap binds often with this size of universe and
# a few years of daily data, which is itself the point.
MAX_SHRINKAGE = 0.90


def shrunk_expected_returns(
    prices: pd.DataFrame, prior: pd.Series | None = None, frequency: int = 252
) -> pd.Series:
    daily_returns = prices.pct_change().dropna()
    n_assets = daily_returns.shape[1]
    n_obs = daily_returns.shape[0]

    sample_mean = daily_returns.mean()

    if prior is None:
        prior_daily = pd.Series(sample_mean.mean(), index=sample_mean.index)
    else:
        prior_daily = (1 + prior.reindex(sample_mean.index)) ** (1 / frequency) - 1

    sample_var = daily_returns.var()
    estimation_var = sample_var / n_obs  # variance of the sample mean itself
    avg_estimation_var = estimation_var.mean()

    dispersion = float(((sample_mean - prior_daily) ** 2).sum())
    if dispersion <= 0 or n_assets <= 3:
        shrinkage = MAX_SHRINKAGE
    else:
        shrinkage = (n_assets - 3) * avg_estimation_var / dispersion
        shrinkage = min(max(shrinkage, 0.0), MAX_SHRINKAGE)

    shrunk_daily = prior_daily + (1 - shrinkage) * (sample_mean - prior_daily)
    return (1 + shrunk_daily) ** frequency - 1


def shrinkage_intensity(prices: pd.DataFrame, prior: pd.Series | None = None) -> float:
    """How much shrinkage shrunk_expected_returns actually applied (0=none, 1=full)."""
    daily_returns = prices.pct_change().dropna()
    n_assets = daily_returns.shape[1]
    n_obs = daily_returns.shape[0]

    sample_mean = daily_returns.mean()
    if prior is None:
        prior_daily = pd.Series(sample_mean.mean(), index=sample_mean.index)
    else:
        prior_daily = (1 + prior.reindex(sample_mean.index)) ** (1 / 252) - 1

    sample_var = daily_returns.var()
    avg_estimation_var = (sample_var / n_obs).mean()
    dispersion = float(((sample_mean - prior_daily) ** 2).sum())

    if dispersion <= 0 or n_assets <= 3:
        return MAX_SHRINKAGE
    return float(min(max((n_assets - 3) * avg_estimation_var / dispersion, 0.0), MAX_SHRINKAGE))
