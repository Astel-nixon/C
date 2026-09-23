"""API layer (CLAUDE.md Step 3).

Wraps the existing pipeline (client_profile -> optimizer -> risk_engine
-> stress_test -> goal_simulator -> explainability) behind FastAPI so a
UI -- including the existing wealth_demo.html -- could eventually call
it live, instead of only running through main.py's two hardcoded
clients. This is a research/recommendation API, not an execution one:
there is deliberately no endpoint that turns a recommendation into a
trade (CLAUDE.md Principle 6). Adding one later needs the human-review
step (Step 8) to exist first, not as a follow-up.
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import db
from client_profile import ClientProfile, Goal
from data_source import get_prices
from main import run_for_client

DB_PATH = os.environ.get("WEALTHAI_DB_PATH", str(db.DEFAULT_DB_PATH))

app = FastAPI(title="WealthAI API", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db(DB_PATH)


class GoalIn(BaseModel):
    name: str
    target_amount: float = Field(gt=0)
    target_date: date
    priority: int = 1
    min_liquidity_required: float = 0.0


class ClientIn(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)
    annual_income: float = Field(ge=0)
    net_worth: float
    liquid_assets: float = Field(ge=0)
    risk_tolerance: float = Field(ge=0, le=1)
    investment_horizon_years: float = Field(ge=0)
    liquidity_need_years: float = Field(ge=0)
    income_stability: float = Field(ge=0, le=1)
    debt_to_income: float = Field(ge=0)
    crypto_cap: float = Field(default=0.05, ge=0, le=1)
    min_cash: float = Field(default=0.05, ge=0, le=1)
    excluded_sectors: list[str] = Field(default_factory=list)
    goals: list[GoalIn] = Field(default_factory=list)


class ClientOut(ClientIn):
    id: int
    risk_capacity: float
    effective_risk_score: float


def _profile_from_in(client_in: ClientIn) -> ClientProfile:
    return ClientProfile(
        name=client_in.name, age=client_in.age, annual_income=client_in.annual_income,
        net_worth=client_in.net_worth, liquid_assets=client_in.liquid_assets,
        risk_tolerance=client_in.risk_tolerance,
        investment_horizon_years=client_in.investment_horizon_years,
        liquidity_need_years=client_in.liquidity_need_years,
        income_stability=client_in.income_stability, debt_to_income=client_in.debt_to_income,
        crypto_cap=client_in.crypto_cap, min_cash=client_in.min_cash,
        excluded_sectors=client_in.excluded_sectors,
        goals=[
            Goal(name=g.name, target_amount=g.target_amount, target_date=g.target_date,
                 priority=g.priority, min_liquidity_required=g.min_liquidity_required)
            for g in client_in.goals
        ],
    )


def _out_from_profile(client_id: int, profile: ClientProfile) -> ClientOut:
    return ClientOut(
        id=client_id, name=profile.name, age=profile.age, annual_income=profile.annual_income,
        net_worth=profile.net_worth, liquid_assets=profile.liquid_assets,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon_years=profile.investment_horizon_years,
        liquidity_need_years=profile.liquidity_need_years,
        income_stability=profile.income_stability, debt_to_income=profile.debt_to_income,
        crypto_cap=profile.crypto_cap, min_cash=profile.min_cash,
        excluded_sectors=profile.excluded_sectors,
        goals=[
            GoalIn(name=g.name, target_amount=g.target_amount, target_date=g.target_date,
                   priority=g.priority, min_liquidity_required=g.min_liquidity_required)
            for g in profile.goals
        ],
        risk_capacity=profile.risk_capacity, effective_risk_score=profile.effective_risk_score,
    )


class RecommendationOut(BaseModel):
    id: int
    client_id: int
    created_at: str
    code_version: str
    data_version: str
    weights: dict[str, float]
    expected_annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    risk_metrics: dict[str, float]
    stress_results: dict[str, float]
    goal_result: dict | None
    explanation: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/clients", response_model=ClientOut, status_code=201)
def create_client(client_in: ClientIn) -> ClientOut:
    profile = _profile_from_in(client_in)
    client_id = db.save_client(profile, db_path=DB_PATH)
    return _out_from_profile(client_id, profile)


@app.get("/clients/{client_id}", response_model=ClientOut)
def get_client(client_id: int) -> ClientOut:
    profile = db.get_client(client_id, db_path=DB_PATH)
    if profile is None:
        raise HTTPException(status_code=404, detail="client not found")
    return _out_from_profile(client_id, profile)


@app.post("/clients/{client_id}/recommendations", response_model=RecommendationOut, status_code=201)
def create_recommendation(client_id: int) -> RecommendationOut:
    profile = db.get_client(client_id, db_path=DB_PATH)
    if profile is None:
        raise HTTPException(status_code=404, detail="client not found")

    prices, data_version = get_prices(years=5, seed=42)
    report = run_for_client(profile, prices)
    recommendation_id = db.save_recommendation(client_id, report, data_version, db_path=DB_PATH)

    stored = db.get_recommendation(recommendation_id, db_path=DB_PATH)
    return RecommendationOut(**stored)


@app.get("/clients/{client_id}/recommendations", response_model=list[RecommendationOut])
def list_client_recommendations(client_id: int) -> list[RecommendationOut]:
    if db.get_client(client_id, db_path=DB_PATH) is None:
        raise HTTPException(status_code=404, detail="client not found")
    return [RecommendationOut(**r) for r in db.list_recommendations(client_id, db_path=DB_PATH)]


@app.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(recommendation_id: int) -> RecommendationOut:
    stored = db.get_recommendation(recommendation_id, db_path=DB_PATH)
    if stored is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return RecommendationOut(**stored)
