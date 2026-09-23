"""Goal-based Monte Carlo simulation (master plan Part A §15/§16).

Uses a Student-t shock distribution rather than i.i.d. normal sampling:
normal sampling understates tail risk and ignores the fat tails real
markets exhibit (master plan Part B §2.9). The t-distribution is scaled
so its variance matches the target annual volatility regardless of the
chosen degrees of freedom.
"""

from __future__ import annotations

import numpy as np


def simulate_goal_probability(
    initial_capital: float,
    annual_contribution: float,
    expected_return: float,
    annual_volatility: float,
    years: float,
    target_amount: float,
    n_simulations: int = 10000,
    t_dof: int = 5,
    seed: int | None = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    n_years = max(int(round(years)), 1)

    # Student-t variance is dof / (dof - 2); rescale so simulated annual
    # vol matches the requested annual_volatility regardless of t_dof.
    t_scale = annual_volatility / np.sqrt(t_dof / (t_dof - 2))
    shocks = rng.standard_t(t_dof, size=(n_simulations, n_years)) * t_scale
    annual_returns = expected_return + shocks

    trajectory = np.zeros((n_simulations, n_years + 1))
    trajectory[:, 0] = initial_capital
    balances = np.full(n_simulations, initial_capital, dtype=float)
    for year in range(n_years):
        balances = balances * (1 + annual_returns[:, year]) + annual_contribution
        balances = np.maximum(balances, 0.0)
        trajectory[:, year + 1] = balances

    final_balances = trajectory[:, -1]
    probability_of_success = float(np.mean(final_balances >= target_amount))
    percentiles = {p: float(np.percentile(final_balances, p)) for p in (5, 25, 50, 75, 95)}

    return {
        "probability_of_success": probability_of_success,
        "percentiles": percentiles,
        "median_outcome": percentiles[50],
        "target_amount": target_amount,
        "years": years,
    }
