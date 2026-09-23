"""Persistent storage.

Plain sqlite3, not an ORM -- the schema is small (clients, goals,
recommendations, review_queue) and a thin functional layer over raw SQL
is easier to read end-to-end than an ORM's indirection at this scale.
Each function opens and closes its own connection: simplest thing
that's safe across FastAPI's threaded request handling, at a scale
where connection-pooling overhead doesn't matter yet.

Every recommendation carries three separate version markers, on
purpose: code_version (git short SHA -- which commit ran), data_version
(from data_source.get_prices -- which market data), and model_version
(see version.py -- which optimization methodology). A commit can change
without the methodology changing (a comment fix, a test), so collapsing
all three into one field would make "did the numbers change because the
world changed or because the code changed" unanswerable later.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from client_profile import ClientProfile, Goal
from version import MODEL_VERSION

DEFAULT_DB_PATH = Path(__file__).parent / "wealthai.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    annual_income REAL NOT NULL,
    net_worth REAL NOT NULL,
    liquid_assets REAL NOT NULL,
    risk_tolerance REAL NOT NULL,
    investment_horizon_years REAL NOT NULL,
    liquidity_need_years REAL NOT NULL,
    income_stability REAL NOT NULL,
    debt_to_income REAL NOT NULL,
    crypto_cap REAL NOT NULL,
    illiquid_cap REAL NOT NULL,
    min_cash REAL NOT NULL,
    excluded_sectors TEXT NOT NULL,
    tax_jurisdiction TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    target_date TEXT NOT NULL,
    priority INTEGER NOT NULL,
    min_liquidity_required REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    created_at TEXT NOT NULL,
    code_version TEXT NOT NULL,
    data_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    weights TEXT NOT NULL,
    expected_annual_return REAL NOT NULL,
    annual_volatility REAL NOT NULL,
    sharpe_ratio REAL NOT NULL,
    risk_metrics TEXT NOT NULL,
    stress_results TEXT NOT NULL,
    goal_result TEXT,
    tax_result TEXT,
    explanation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL REFERENCES recommendations(id),
    client_id INTEGER NOT NULL REFERENCES clients(id),
    status TEXT NOT NULL DEFAULT 'pending',
    proposed_weights TEXT NOT NULL,
    previous_weights TEXT,
    reviewer_note TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
"""


def get_code_version() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


@contextmanager
def _connect(db_path: Path | str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_client(profile: ClientProfile, db_path: Path | str = DEFAULT_DB_PATH) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO clients
               (name, age, annual_income, net_worth, liquid_assets, risk_tolerance,
                investment_horizon_years, liquidity_need_years, income_stability,
                debt_to_income, crypto_cap, illiquid_cap, min_cash, excluded_sectors,
                tax_jurisdiction, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.name, profile.age, profile.annual_income, profile.net_worth,
                profile.liquid_assets, profile.risk_tolerance, profile.investment_horizon_years,
                profile.liquidity_need_years, profile.income_stability, profile.debt_to_income,
                profile.crypto_cap, profile.illiquid_cap, profile.min_cash,
                json.dumps(profile.excluded_sectors), profile.tax_jurisdiction,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        client_id = cur.lastrowid
        for goal in profile.goals:
            conn.execute(
                """INSERT INTO goals
                   (client_id, name, target_amount, target_date, priority, min_liquidity_required)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (client_id, goal.name, goal.target_amount, goal.target_date.isoformat(),
                 goal.priority, goal.min_liquidity_required),
            )
        return client_id


def get_client(client_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> ClientProfile | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if row is None:
            return None
        goal_rows = conn.execute("SELECT * FROM goals WHERE client_id = ?", (client_id,)).fetchall()
        goals = [
            Goal(
                name=g["name"], target_amount=g["target_amount"],
                target_date=datetime.fromisoformat(g["target_date"]).date(),
                priority=g["priority"], min_liquidity_required=g["min_liquidity_required"],
            )
            for g in goal_rows
        ]
        return ClientProfile(
            name=row["name"], age=row["age"], annual_income=row["annual_income"],
            net_worth=row["net_worth"], liquid_assets=row["liquid_assets"],
            risk_tolerance=row["risk_tolerance"],
            investment_horizon_years=row["investment_horizon_years"],
            liquidity_need_years=row["liquidity_need_years"],
            income_stability=row["income_stability"], debt_to_income=row["debt_to_income"],
            goals=goals, crypto_cap=row["crypto_cap"], illiquid_cap=row["illiquid_cap"],
            min_cash=row["min_cash"], excluded_sectors=json.loads(row["excluded_sectors"]),
            tax_jurisdiction=row["tax_jurisdiction"],
        )


def save_recommendation(
    client_id: int, report: dict, data_version: str, db_path: Path | str = DEFAULT_DB_PATH
) -> int:
    result = report["portfolio"]
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO recommendations
               (client_id, created_at, code_version, data_version, model_version, weights,
                expected_annual_return, annual_volatility, sharpe_ratio,
                risk_metrics, stress_results, goal_result, tax_result, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id, datetime.now(timezone.utc).isoformat(), get_code_version(), data_version,
                MODEL_VERSION, json.dumps(result.weights), result.expected_annual_return,
                result.annual_volatility, result.sharpe_ratio, json.dumps(report["risk_metrics"]),
                json.dumps(report["stress_results"]),
                json.dumps(report["goal_result"]) if report["goal_result"] else None,
                json.dumps(report["tax_result"]) if report.get("tax_result") else None,
                report["explanation"],
            ),
        )
        return cur.lastrowid


def get_recommendation(recommendation_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)
        ).fetchone()
        if row is None:
            return None
        return _recommendation_row_to_dict(row)


def list_recommendations(client_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM recommendations WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
        return [_recommendation_row_to_dict(row) for row in rows]


def _recommendation_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "created_at": row["created_at"],
        "code_version": row["code_version"],
        "data_version": row["data_version"],
        "model_version": row["model_version"],
        "weights": json.loads(row["weights"]),
        "expected_annual_return": row["expected_annual_return"],
        "annual_volatility": row["annual_volatility"],
        "sharpe_ratio": row["sharpe_ratio"],
        "risk_metrics": json.loads(row["risk_metrics"]),
        "stress_results": json.loads(row["stress_results"]),
        "goal_result": json.loads(row["goal_result"]) if row["goal_result"] else None,
        "tax_result": json.loads(row["tax_result"]) if row["tax_result"] else None,
        "explanation": row["explanation"],
    }


# -- Human review queue --
#
# No endpoint anywhere turns a recommendation into a trade, so this
# queue isn't gating real execution yet -- it exists so that workflow
# exists in the codebase before anything needs it, rather than being a
# thing to "add later" once there's suddenly a reason to skip it.

def last_approved_weights(client_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """SELECT proposed_weights FROM review_queue
               WHERE client_id = ? AND status = 'approved'
               ORDER BY decided_at DESC LIMIT 1""",
            (client_id,),
        ).fetchone()
        return json.loads(row["proposed_weights"]) if row else None


def submit_for_review(
    recommendation_id: int, client_id: int, db_path: Path | str = DEFAULT_DB_PATH
) -> int:
    recommendation = get_recommendation(recommendation_id, db_path=db_path)
    if recommendation is None:
        raise ValueError(f"no such recommendation: {recommendation_id}")
    previous = last_approved_weights(client_id, db_path=db_path)

    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO review_queue
               (recommendation_id, client_id, status, proposed_weights, previous_weights, created_at)
               VALUES (?, ?, 'pending', ?, ?, ?)""",
            (
                recommendation_id, client_id, json.dumps(recommendation["weights"]),
                json.dumps(previous) if previous is not None else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


def decide_review(
    review_id: int, decision: str, reviewer_note: str = "", db_path: Path | str = DEFAULT_DB_PATH
) -> dict | None:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    with _connect(db_path) as conn:
        conn.execute(
            """UPDATE review_queue SET status = ?, reviewer_note = ?, decided_at = ?
               WHERE id = ? AND status = 'pending'""",
            (decision, reviewer_note, datetime.now(timezone.utc).isoformat(), review_id),
        )
    return get_review(review_id, db_path=db_path)


def get_review(review_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM review_queue WHERE id = ?", (review_id,)).fetchone()
        if row is None:
            return None
        return _review_row_to_dict(row)


def list_reviews(status: str | None = None, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM review_queue WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM review_queue ORDER BY created_at DESC").fetchall()
        return [_review_row_to_dict(row) for row in rows]


def _review_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "recommendation_id": row["recommendation_id"],
        "client_id": row["client_id"],
        "status": row["status"],
        "proposed_weights": json.loads(row["proposed_weights"]),
        "previous_weights": json.loads(row["previous_weights"]) if row["previous_weights"] else None,
        "reviewer_note": row["reviewer_note"],
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
    }
