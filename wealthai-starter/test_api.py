"""Property-based checks on the API + storage layer (CLAUDE.md Principle 5).

Same pattern as test_pipeline.py: plain asserts, one isolated temp
SQLite DB per check via FastAPI's in-process TestClient -- no real
network port, no shared state between checks.
"""

from __future__ import annotations

import tempfile
import traceback

import api
from fastapi.testclient import TestClient

_checks: list[tuple[str, callable]] = []


def check(name):
    def decorator(fn):
        _checks.append((name, fn))
        return fn

    return decorator


def _fresh_client() -> TestClient:
    api.DB_PATH = tempfile.mktemp(suffix=".db")
    return TestClient(api.app)


SAMPLE_CLIENT = {
    "name": "API Test Client", "age": 30, "annual_income": 100_000, "net_worth": 150_000,
    "liquid_assets": 100_000, "risk_tolerance": 0.7, "investment_horizon_years": 25,
    "liquidity_need_years": 5, "income_stability": 0.8, "debt_to_income": 0.1,
    "goals": [{"name": "Retirement", "target_amount": 1_500_000, "target_date": "2050-01-01"}],
}


@check("health endpoint responds")
def _():
    with _fresh_client() as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


@check("create client returns effective_risk_score capped by capacity")
def _():
    with _fresh_client() as client:
        r = client.post("/clients", json=SAMPLE_CLIENT)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"] > 0
        assert body["effective_risk_score"] <= body["risk_tolerance"]
        assert body["effective_risk_score"] <= body["risk_capacity"]


@check("get client round-trips goals")
def _():
    with _fresh_client() as client:
        created = client.post("/clients", json=SAMPLE_CLIENT).json()
        r = client.get(f"/clients/{created['id']}")
        assert r.status_code == 200
        body = r.json()
        assert len(body["goals"]) == 1
        assert body["goals"][0]["name"] == "Retirement"


@check("get client 404s for unknown id")
def _():
    with _fresh_client() as client:
        r = client.get("/clients/999999")
        assert r.status_code == 404


@check("recommendation weights sum to 1 and persist")
def _():
    with _fresh_client() as client:
        created = client.post("/clients", json=SAMPLE_CLIENT).json()
        r = client.post(f"/clients/{created['id']}/recommendations")
        assert r.status_code == 201, r.text
        rec = r.json()
        assert abs(sum(rec["weights"].values()) - 1.0) < 1e-3
        assert rec["code_version"]
        assert rec["data_version"].startswith("synthetic:")

        fetched = client.get(f"/recommendations/{rec['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["weights"] == rec["weights"]


@check("recommendation for unknown client 404s")
def _():
    with _fresh_client() as client:
        r = client.post("/clients/999999/recommendations")
        assert r.status_code == 404


@check("recommendations list grows with repeated requests")
def _():
    with _fresh_client() as client:
        created = client.post("/clients", json=SAMPLE_CLIENT).json()
        client.post(f"/clients/{created['id']}/recommendations")
        client.post(f"/clients/{created['id']}/recommendations")
        r = client.get(f"/clients/{created['id']}/recommendations")
        assert r.status_code == 200
        assert len(r.json()) == 2


@check("two clients with different risk tolerance get different portfolios via the API")
def _():
    with _fresh_client() as client:
        conservative = dict(SAMPLE_CLIENT, name="Conservative", risk_tolerance=0.15)
        aggressive = dict(SAMPLE_CLIENT, name="Aggressive", risk_tolerance=0.95)

        c1 = client.post("/clients", json=conservative).json()
        c2 = client.post("/clients", json=aggressive).json()

        rec1 = client.post(f"/clients/{c1['id']}/recommendations").json()
        rec2 = client.post(f"/clients/{c2['id']}/recommendations").json()

        assert rec1["annual_volatility"] != rec2["annual_volatility"]


@check("invalid client payload is rejected with 422")
def _():
    with _fresh_client() as client:
        bad = dict(SAMPLE_CLIENT, risk_tolerance=1.5)  # out of [0, 1] range
        r = client.post("/clients", json=bad)
        assert r.status_code == 422


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
