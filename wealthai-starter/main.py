"""Stage 1 research prototype entry point (master plan Part C).

Defines two client profiles with different risk tolerances but identical
crypto/ethical constraints, runs each through the optimizer, and prints
the resulting allocations side by side. The two portfolios coming out
differently is the point: it demonstrates Part A §2's central claim ("two
people looking at exactly the same market should potentially receive
completely different recommendations") is actually true in code, now that
risk_tolerance selects a frontier point instead of always solving for
max-Sharpe (see Part C §C4).
"""

from __future__ import annotations

from dataclasses import dataclass

from portfolio_optimizer import PortfolioResult, optimize_portfolio
from synthetic_data import generate_synthetic_prices


@dataclass
class ClientProfile:
    name: str
    age: int
    risk_tolerance: float  # 0 (max capital preservation) .. 1 (max growth)
    crypto_cap: float
    min_cash: float


CLIENT_A = ClientProfile(
    name="Client A",
    age=28,
    risk_tolerance=0.85,
    crypto_cap=0.05,
    min_cash=0.05,
)

CLIENT_B = ClientProfile(
    name="Client B",
    age=57,
    risk_tolerance=0.20,
    crypto_cap=0.05,
    min_cash=0.05,
)


def run_for_client(profile: ClientProfile, prices) -> PortfolioResult:
    return optimize_portfolio(
        prices,
        risk_tolerance=profile.risk_tolerance,
        crypto_cap=profile.crypto_cap,
        min_cash=profile.min_cash,
    )


def print_result(profile: ClientProfile, result: PortfolioResult) -> None:
    print(f"\n=== {profile.name} (age {profile.age}, risk_tolerance={profile.risk_tolerance}) ===")
    for asset, weight in sorted(result.weights.items(), key=lambda kv: -kv[1]):
        if weight > 0.0001:
            print(f"  {asset:<18} {weight:6.1%}")
    print(f"  {'—' * 26}")
    print(f"  Expected annual return: {result.expected_annual_return:6.1%}")
    print(f"  Annual volatility:      {result.annual_volatility:6.1%}")
    print(f"  Sharpe ratio:           {result.sharpe_ratio:6.2f}")


def main() -> None:
    prices = generate_synthetic_prices(years=5, seed=42)
    print(f"Generated {len(prices)} days of synthetic prices for: {list(prices.columns)}")

    result_a = run_for_client(CLIENT_A, prices)
    result_b = run_for_client(CLIENT_B, prices)

    print_result(CLIENT_A, result_a)
    print_result(CLIENT_B, result_b)

    print(
        "\nSame market data, different risk tolerances -> different portfolios: "
        f"{result_a.annual_volatility:.1%} vol vs {result_b.annual_volatility:.1%} vol."
    )


if __name__ == "__main__":
    main()
