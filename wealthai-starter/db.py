"""Persistent storage (CLAUDE.md Step 2).

Plain sqlite3, not an ORM -- the schema is small (clients, goals,
recommendations) and a thin functional layer over raw SQL is easier to
read end-to-end than an ORM's indirection at this scale. Each function
opens and closes its own connection: simplest thing that's safe across
FastAPI's threaded request handling, at a scale where connection-pooling
overhead doesn't matter yet.

Every recommendation is stored with the code version (git short SHA, so
"which optimizer produced this" is answerable later) and the data
version (from data_source.get_prices) it was generated against -- the
seed of the model-registry principle from CLAUDE.md Section 4, not the
full thing yet.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from client_profile import ClientProfile, Goal

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
    min_cash REAL NOT NULL,
    excluded_sectors TEXT NOT NULL,
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
    weights TEXT NOT NULL,
    expected_annual_return REAL NOT NULL,
    annual_volatility REAL NOT NULL,
    sharpe_ratio REAL NOT NULL,
    risk_metrics TEXT NOT NULL,
    stress_results TEXT NOT NULL,
    goal_result TEXT,
    explanation TEXT NOT NULL
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
                debt_to_income, crypto_cap, min_cash, excluded_sectors, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.name, profile.age, profile.annual_income, profile.net_worth,
                profile.liquid_assets, profile.risk_tolerance, profile.investment_horizon_years,
                profile.liquidity_need_years, profile.income_stability, profile.debt_to_income,
                profile.crypto_cap, profile.min_cash, json.dumps(profile.excluded_sectors),
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
            goals=goals, crypto_cap=row["crypto_cap"], min_cash=row["min_cash"],
            excluded_sectors=json.loads(row["excluded_sectors"]),
        )


def save_recommendation(
    client_id: int, report: dict, data_version: str, db_path: Path | str = DEFAULT_DB_PATH
) -> int:
    result = report["portfolio"]
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO recommendations
               (client_id, created_at, code_version, data_version, weights,
                expected_annual_return, annual_volatility, sharpe_ratio,
                risk_metrics, stress_results, goal_result, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id, datetime.now(timezone.utc).isoformat(), get_code_version(), data_version,
                json.dumps(result.weights), result.expected_annual_return, result.annual_volatility,
                result.sharpe_ratio, json.dumps(report["risk_metrics"]),
                json.dumps(report["stress_results"]),
                json.dumps(report["goal_result"]) if report["goal_result"] else None,
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
        "weights": json.loads(row["weights"]),
        "expected_annual_return": row["expected_annual_return"],
        "annual_volatility": row["annual_volatility"],
        "sharpe_ratio": row["sharpe_ratio"],
        "risk_metrics": json.loads(row["risk_metrics"]),
        "stress_results": json.loads(row["stress_results"]),
        "goal_result": json.loads(row["goal_result"]) if row["goal_result"] else None,
        "explanation": row["explanation"],
    }
