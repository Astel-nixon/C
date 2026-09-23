"""Client profiling engine (master plan Part A §5/§6).

Encodes the platform's central asymmetry: risk TOLERANCE (a client's
stated psychological comfort with volatility) is not the same thing as
risk CAPACITY (what their actual financial situation can absorb).
Capacity caps tolerance -- it is never averaged with it. A client who
says they're fine with a 40% drawdown but needs 80% of their liquid
assets for a house purchase in two years cannot actually take that
risk, no matter what they say on a questionnaire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Goal:
    name: str
    target_amount: float
    target_date: date
    priority: int = 1  # 1 = highest priority
    min_liquidity_required: float = 0.0

    def years_remaining(self, as_of: date | None = None) -> float:
        as_of = as_of or date.today()
        return max((self.target_date - as_of).days / 365.25, 0.0)


@dataclass
class ClientProfile:
    name: str
    age: int
    annual_income: float
    net_worth: float
    liquid_assets: float
    risk_tolerance: float  # 0-1, self-reported comfort with volatility/drawdown
    investment_horizon_years: float
    liquidity_need_years: float  # years until client needs a large chunk of capital
    income_stability: float  # 0-1: 1 = stable salaried income, 0 = highly variable
    debt_to_income: float  # total debt / annual income
    goals: list[Goal] = field(default_factory=list)
    crypto_cap: float = 0.05
    min_cash: float = 0.05
    excluded_sectors: list[str] = field(default_factory=list)  # e.g. ["tobacco", "weapons"]

    @property
    def risk_capacity(self) -> float:
        """0-1 score: how much risk the client's situation can structurally absorb."""
        horizon_score = min(self.investment_horizon_years / 30.0, 1.0)
        liquidity_score = min(self.liquidity_need_years / 10.0, 1.0)
        debt_score = max(1.0 - self.debt_to_income, 0.0)
        structural = 0.4 * horizon_score + 0.3 * liquidity_score + 0.3 * debt_score
        # Unstable income gates capacity further, even with a long horizon.
        return max(0.0, min(1.0, structural * (0.5 + 0.5 * self.income_stability)))

    @property
    def effective_risk_score(self) -> float:
        """The score the optimizer actually uses: capacity CAPS tolerance."""
        return min(self.risk_tolerance, self.risk_capacity)
