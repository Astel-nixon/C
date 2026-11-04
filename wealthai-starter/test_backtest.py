"""Property-based checks on the walk-forward backtest.

Same style as test_pipeline.py / test_api.py: check properties that
matter, not just "did it run."
"""

from __future__ import annotations

import traceback

from backtest import RISK_TOLERANCES, run_backtest, summarize

_checks: list[tuple[str, callable]] = []


def check(name):
    def decorator(fn):
        _checks.append((name, fn))
        return fn

    return decorator


ROWS = run_backtest()
SUMMARY = summarize(ROWS)


@check("every risk_tolerance x window combination produced a row")
def _():
    assert len(ROWS) % len(RISK_TOLERANCES) == 0
    n_windows = len(ROWS) // len(RISK_TOLERANCES)
    assert n_windows >= 5, f"expected several rolling windows, got {n_windows}"


@check("every row has finite, well-formed metrics")
def _():
    required = {
        "window_start_year", "risk_tolerance", "in_sample_expected_return",
        "in_sample_expected_vol", "in_sample_sharpe", "oos_sharpe",
        "oos_vol", "oos_max_drawdown", "baseline_oos_sharpe",
    }
    for row in ROWS:
        assert required.issubset(row.keys())
        for key in required:
            assert row[key] == row[key], f"{key} is NaN"  # NaN != NaN


@check("realized out-of-sample volatility rises with risk tolerance")
def _():
    vols = [SUMMARY[rt]["avg_oos_vol"] for rt in sorted(RISK_TOLERANCES)]
    assert vols == sorted(vols), f"OOS vol is not monotonic in risk tolerance: {vols}"


@check("estimated volatility is a reasonable predictor of realized volatility")
def _():
    for rt, s in SUMMARY.items():
        gap = abs(s["avg_oos_vol"] - s["avg_in_sample_vol"])
        assert gap < 0.05, (
            f"risk_tolerance={rt}: in-sample vol {s['avg_in_sample_vol']:.1%} vs "
            f"realized {s['avg_oos_vol']:.1%} diverge by more than 5 points"
        )


def run_all() -> int:
    passed = failed = 0
    for name, fn in _checks:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
        except Exception:
            print(f"  ERROR {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {len(_checks)} total")
    return failed


if __name__ == "__main__":
    import sys

    sys.exit(1 if run_all() else 0)
