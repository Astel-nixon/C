# AI-Powered Multi-Asset Wealth Management Platform — Master Plan

*Consolidated reference combining the original project vision, the refined technical build plan, and current implementation status. Compiled to be handed to another AI assistant or kept as a standalone project reference — it should be self-contained enough that someone (or something) with no other context can pick up the project from here.*

**How to use this document:** Part A is the philosophy and product requirements (why this exists, what it needs to do). Part B is the concrete engineering plan (what to actually build it with, and why). Part C used to track current build status inline but now just points to `CLAUDE.md` in the repo root, which is the maintained source of truth for that (see C1). If you're feeding this to a model with a small context window: read `CLAUDE.md` first for exactly where the build stands and what to do next, then Part B here for the "why" behind stack choices, then Part A for background/rationale.

---

# PART A — VISION & PHILOSOPHY

## 1. Project Vision

Build an AI-powered wealth-management and investment-intelligence system that evaluates a client's financial circumstances, goals, constraints, risk profile, ethical preferences, tax situation, and investment horizon, then researches opportunities across multiple asset classes and constructs a personalized portfolio.

The platform combines: Natural Language Processing, web and financial-data ingestion, Large Language Models, information extraction, fundamental analysis, quantitative finance, portfolio optimization, risk management, Monte Carlo simulation, tax-aware optimization, client profiling, goal-based financial planning, scenario/stress testing, portfolio monitoring, explainable AI, and human investment oversight.

The system is **not** simply a stock-picking chatbot. Its core purpose:

> Translate a client's personal financial objectives and constraints into an evidence-backed, risk-aware, tax-aware, multi-asset investment strategy.

The eventual system could support a small systematic wealth-management operation or fund, subject to appropriate regulatory, licensing, compliance, custody, and investment-management requirements.

## 2. Core Philosophy

> The optimal investment is not universal. It depends on the investor.

Two people looking at exactly the same market should potentially receive completely different recommendations.

**Client A** — Age 28, high income, long horizon, high risk tolerance, no near-term liquidity requirement, comfortable with crypto. Possible result: 65% Global Equities / 15% Bonds / 10% Alternatives-REITs / 5% Crypto / 5% Cash.

**Client B** — Age 57, retirement in 7 years, moderate risk tolerance, high liquidity requirement, capital preservation priority. Possible result: 35% Global Equities / 45% Bonds / 5% REITs / 5% Gold / 10% Cash.

**Client C** — High risk capacity, ethical constraints (no tobacco, weapons, gambling, fossil fuels), max crypto allocation 3%. Requires a completely different investable universe *before* optimization even starts.

The architecture must treat the **client profile as a first-class input**, rather than generating an investment thesis first and trying to fit the client afterward.

## 3. The Fundamental Architecture

```
                    CLIENT
                      │
           Client Profiling Engine
                      │
             Client Constraints
                      │
MARKET DATA ──────────┼────────── WEB DATA
    │                 │               │
Financial Data        │         NLP / LLM Engine
    │                 │               │
    └────────────┬────┴───────┬───────┘
                 ↓            ↓
             Feature & Signal Engine
                       ↓
               Investment Universe
                       ↓
              Opportunity Analysis
                       ↓
               Portfolio Optimizer
                       │
           ┌───────────┼────────────┐
        Risk        Tax Engine   Goal Engine
        Engine                    │
           └───────────┼────────────┘
                Scenario Engine
                       ↓
             Portfolio Recommendation
                       ↓
                Explainability
                       ↓
              Human Investment Review
                       ↓
                  Execution
                       ↓
              Continuous Monitoring
```

## 4. What Problem Is the System Solving?

Traditional investment systems separate investment research, portfolio construction, financial planning, risk analysis, tax planning, and client profiling. This platform unifies them.

Central optimization problem:

```
max_w  U(w) = E[R_p] − λ·Risk_p − γ·Drawdown_p − τ·TaxCost_p − η·GoalFailureProbability
```

subject to client-specific constraints, e.g.:

```
Σ w_i = 1
w_crypto ≤ 0.05
w_tobacco = 0
w_weapons = 0
Liquidity ≥ $50,000
P(GoalFailure) < 10%
```

and any other constraints appropriate to the client and regulatory framework.

## 5. Client Profiling Engine

**Personal/financial information:** age, income, net worth, liquid assets, existing investments, liabilities, debt, monthly expenses, savings rate, expected income growth, dependents.

**Investment characteristics:** risk tolerance, risk capacity, investment horizon, liquidity needs, investment experience, existing exposure, preferred asset classes.

**Goals** (each with target amount, target date, priority, required liquidity, acceptable failure probability): retirement, home purchase, education, wealth preservation, legacy, early retirement, income generation, capital growth.

**Ethical preferences:** ESG requirements, religious/ethical restrictions, tobacco/weapons/gambling/fossil-fuel exclusion, specific corporate exclusions, country exclusions, environmental preferences.

**Geographic/tax profile:** country of residence, tax jurisdiction, citizenship, account type, currency, cross-border constraints.

## 6. Risk Profiling

Distinguish **risk tolerance** (psychological willingness to accept volatility/drawdown) from **risk capacity** (what the client's actual financial circumstances can support). Someone comfortable with a 40% drawdown but needing 80% of their wealth for a house purchase in two years has low risk *capacity* regardless of stated tolerance. Don't treat a questionnaire score as the entire risk model:

```
RiskScore = f(Tolerance, Capacity, Horizon, Liquidity, IncomeStability, Debt, GoalCriticality)
```

## 7. Market and Web Data Engine

**Structured data:** equity prices, bond yields, ETF data, commodity prices, crypto prices, FX, interest rates, inflation, GDP, employment, company financials, earnings, balance sheets, cash flows, valuation ratios.

**Unstructured data:** news, company announcements, earnings transcripts, research, blogs, government/economic publications, industry publications, corporate filings, regulatory announcements, alternative datasets.

Goal is not maximum scraping — it's a reliable information layer with source provenance, timestamps, deduplication, credibility scoring, freshness, entity identification, event extraction, confidence scoring.

## 8. NLP Pipeline

```
Raw Documents → Cleaning → Language Detection → Document Classification →
NER → Entity Linking → Event Extraction → Relationship Extraction →
Sentiment/Stance → Topic Classification → Time Horizon Extraction →
Impact Estimation → Structured Investment Signal
```

Example: a semiconductor manufacturer announces a supply-chain disruption. The NLP system extracts company, event type, sector, expected duration, expected impact, potential financial impact, sentiment, confidence score, source, timestamp — and writes it to a structured event database rather than directly instructing a buy/sell.

## 9. LLM's Role

The LLM reasons over information; it does not decide trades.

**Good uses:** document summarization, information extraction, event classification, financial Q&A, comparing investment theses, generating rationales, explaining decisions, client communication, identifying conflicting information, natural-language interaction.

**Not appropriate:** "LLM, decide which stocks to buy."

```
Raw information → LLM/NLP → Structured evidence → Quantitative models →
Optimizer → Risk controls → Recommendation
```

## 10. Investment Universe

**Equities** (stocks, ETFs, index funds) · **Fixed income** (govt/corporate bonds, bond ETFs, money-market) · **Real estate** (REITs, listed vehicles) · **Commodities** (gold, silver, energy, commodity funds) · **Crypto** (BTC, ETH, others where appropriate) · **Alternatives** (private markets, infrastructure, hedge funds, private credit, venture — eligibility-dependent) · **Cash** (a portfolio component, not an afterthought).

## 11. Standardizing Different Asset Classes

Every investment gets a common representation: expected return, volatility, drawdown, liquidity, correlation, duration, credit risk, currency exposure, geographic exposure, factor exposure, valuation, tax characteristics, ESG characteristics, data confidence, transaction cost. The goal isn't to pretend assets are identical — it's enough common structure for an optimizer to compare them.

## 12. Opportunity Scoring

Multiple scores per asset (fundamental, valuation, momentum, macro, sentiment, risk, liquidity, tax, ESG, data confidence) combined as:

```
OpportunityScore_i = Σ_k w_k · Score_ik
```

This is an **input to portfolio construction**, never an automatic buy signal.

## 13. Investment Thesis Engine

For every significant candidate: Thesis, Catalysts, Risks, Time horizon, Confidence, Evidence, and **Contrarian evidence** — this last one prevents the system from becoming an automated confirmation machine.

## 14. Portfolio Construction

Support multiple methods rather than one: **Mean-variance optimization**, **Risk parity**, **Black-Litterman**, **CVaR optimization**, **Goal-based optimization**, **Robust optimization** (accounting for estimation uncertainty).

## 15. Goal-Based Wealth Management

Each client has one or more goals (amount, date, priority). Run Monte Carlo simulations to estimate P(Goal Achieved) per goal, then let the optimizer adjust allocation to improve those probabilities.

## 16. Monte Carlo Engine

Simulate many possible futures rather than one deterministic forecast. Show the client a distribution (5th/25th/median/75th/95th percentile outcomes), plus probability of reaching target, probability of shortfall, probability of severe drawdown, required savings, required return, safe withdrawal range.

## 17. Risk Engine

Metrics: volatility, VaR, Expected Shortfall, max drawdown, Sharpe, Sortino, beta, tracking error, concentration, factor exposures, liquidity, currency exposure, duration, credit exposure. Must surface **hidden concentration** — e.g., separate Apple stock + S&P 500 ETF + NASDAQ ETF + Tech ETF holdings can add up to much larger effective tech exposure than any single line item suggests.

## 18. Scenario and Stress Testing

Test the portfolio against: equity crash (-40%), rate shock (+300bps), inflation shock, recession, crypto crash (-70%), currency shock, and historical analogues (GFC, COVID, inflationary periods, major rate cycles). Goal: understand how badly the portfolio can behave under plausible adverse conditions — not predict the next crisis.

## 19. Tax Optimization

Tax-loss harvesting, capital gains realization, asset location, withdrawal sequencing, dividend/interest considerations, rebalancing tax impact, tax-efficient fund selection, cross-border considerations. Highly jurisdiction-specific. A slightly-lower-return portfolio with much lower tax drag can be the better choice for the right client.

## 20. Ethical Investment Engine

Client-specified exclusions (tobacco, weapons, gambling, fossil fuels) and preferences (renewables, healthcare, social impact, governance). The system must distinguish revenue exposure, direct involvement, supply-chain involvement, ownership, controversy, and third-party ESG ratings — and be able to explain *why* a security passed or failed the screen.

## 21. Explainability

Every recommendation is explainable — e.g., "why 8% in Asset X" broken into diversification benefit, correlation with dominant exposure, goal-probability impact, ethical compliance, liquidity fit, tax characteristics — backed by evidence.

## 22. Source Provenance

Full audit trail: Recommendation → Model version → Features used → Events extracted → Data sources → Original documents → Timestamps. Must be able to answer "why did the model make this recommendation on August 20?" — essential for debugging, compliance, client communication, research, model validation, governance.

## 23. Data Quality System

Guard against duplicate stories, fake news, SEO spam, outdated/incorrect data, conflicting sources, look-ahead bias, survivorship bias, data leakage, manipulated narratives. Each source gets a reliability score, recency, primary/secondary flag, historical accuracy, conflict status, confidence. Prefer primary sources > official disclosures > regulatory sources > high-quality datasets > reputable journalism > lower-confidence sources, with uncertainty clearly labeled.

## 24. Backtesting

Avoid look-ahead bias, survivorship bias, selection bias, data leakage. Include transaction costs (commissions, spreads, slippage, market impact) and taxes where appropriate. Report annual return, volatility, Sharpe, Sortino, max drawdown, turnover, transaction costs, tax drag, win rate, worst/best year.

## 25. Paper Trading

```
Live market data → System recommendations → Paper portfolio → Real-time monitoring
```

No real money initially. Tests latency, data quality, recommendation stability, turnover, model drift, edge cases.

## 26. Portfolio Monitoring

Continuous monitoring of market changes, client financial changes, risk drift, allocation drift, new opportunities, tax opportunities, liquidity, goal probability, regulatory changes, concentration — with automatic detection of threshold breaches (e.g., equity allocation drifting from 50% target to 59% actual triggers a rebalance recommendation).

## 27. Client Digital Twin

A structured, continuously-updated representation of the client's entire financial life (age, income, net worth, liquid assets, debt, risk tolerance/capacity, horizon, goals, liquidity requirement, ethical restrictions, crypto limit, tax jurisdiction). When something changes, the system reassesses the portfolio.

## 28. User Interface

Client dashboard shows net worth, invested amount, cash, portfolio return, expected return range, risk level, max historical/stress drawdown, goal-achievement probability, current allocation, and recommended actions (e.g., rebalance with estimated tax impact and reasoning).

## 29. Natural-Language Interface

Clients ask things like "Can I afford a $1M house in five years?" or "What happens if the market falls 30%?" or "I want less risk without hurting my retirement probability much." The LLM is the conversational layer; the numerical engines stay deterministic and auditable underneath.

## 30. Human-in-the-Loop Architecture

Not `AI → automatic trades`. Instead:

```
AI → Research → Quant model → Portfolio recommendation → Risk/compliance
checks → Human investment professional → Approval → Execution
```

This dramatically reduces catastrophic-model-behavior risk. Some low-risk processes can be automated later under appropriate controls.

## 31. Fund Version

Same architecture, different question: not "what should Client A buy?" but "what should the fund hold under Strategy X?" — Market Research → NLP Signals → Factor Models → Opportunity Ranking → Portfolio Optimization → Risk Limits → Portfolio. Different clients can then map to different strategies.

## 32. Business Models

**SaaS** (sell to wealth managers/advisors) · **B2C** (clients use directly) · **Investment research platform** (sell intelligence) · **Fund infrastructure** (operate a systematic fund internally) · **Hybrid** (software/research first, investment-management business later — probably the most practical startup route).

## 33. What NOT to Build Initially

Not simultaneously: every country, every asset class, fully autonomous trading, perfect tax optimization, private markets, direct physical real estate, every cryptocurrency, every possible goal, universal ethical classification.

## 34. Minimum Viable Product

**Client inputs:** capital, age, income, risk, horizon, goals, liquidity, ethical constraints, crypto limit, tax jurisdiction.
**Universe:** global equities, ETFs, government bonds, gold, REITs, Bitcoin, cash.
**Data:** reliable market data + a small set of high-quality news/filing sources.
**Models:** return estimation, volatility, correlation, risk scoring, portfolio optimization, Monte Carlo, goal probability, simple tax estimation, ethical screening.
**Output:** recommended portfolio, expected return range, volatility, drawdown, goal probability, scenario analysis, explanation, evidence.

## 35–37. Original Stack Sketch, DB Schema, Model Governance

*(Superseded by Part B below, which names concrete tools and gives rationale. Original DB table list retained for reference: `clients, client_goals, client_constraints, client_accounts, assets, asset_prices, asset_fundamentals, asset_classifications, documents, document_entities, document_events, investment_signals, portfolio_models, portfolio_recommendations, portfolio_positions, risk_metrics, tax_rules, transactions, model_versions, audit_logs`. Every model needs: name, version, training date/dataset, features, hyperparameters, performance, known limitations, validation results, deployment date.)*

## 38. Security

Authentication, authorization, encryption, secrets management, audit logging, access controls, data retention, backup, monitoring. Client financial data is never treated like ordinary application data.

## 39. Regulatory/Compliance Layer

Determine: jurisdiction, whether the activity is research/advice/portfolio management/fund management, client eligibility, required disclosures, suitability obligations, marketing restrictions, recordkeeping, licensing, permitted custody arrangements. For Singapore specifically, this needs to be designed around the applicable MAS framework and exact business activity — compliance controls belong in the architecture from the start, not bolted on after. *(See Part B §3 for the concrete framework.)*

## 40. Key Principle: AI Should Not Invent Numbers

Never let an LLM casually produce "Expected return = 14.7%" without a quantitative model behind it. LLM → interpretation; Quantitative model → numerical estimate. *(See Part B §2.6 for the concrete implementation pattern.)*

## 41. Key Principle: Every Recommendation Needs Evidence

Recommendation, Confidence, Supporting evidence, Contradicting evidence, Model assumptions, Risk, Expected impact, Time horizon, Data timestamp — closer to an AI investment analyst than an AI fortune teller.

## 42. Key Principle: Uncertainty Must Be Explicit

The system must be able to say "low confidence" rather than forcing every asset into a strong recommendation.

## 43. Main Technical Challenges

Predicting returns · data quality · cross-asset modelling · correlations that change · regime changes · NLP signal quality (does sentiment survive transaction costs?) · tax complexity · ethical classification ambiguity · backtest realism · regulatory responsibility.

## 44. Potential Research Directions

Regime detection (HMMs, clustering, Bayesian, neural) · NLP alpha validation after costs · graph-based finance (company → supplier → industry → country → commodity → macro factor propagation) · alternative data (satellite, web traffic, job postings, search trends, shipping) · reinforcement learning (only after strong baselines, for rebalancing/execution) · causal modelling (mechanism, not just correlation).

## 45. Investment Signal Pipeline

```
Fundamental analysis → Valuation → Technical/momentum → Macro exposure →
NLP event signals → Sentiment → Risk → Liquidity → Tax → Ethical
constraints → Client suitability → Portfolio contribution
```

The real question is never just "is this a good investment?" — it's "is this investment appropriate for *this client*, in *this portfolio*, *at this time*, under *this client's constraints*?"

## 46. Example End-to-End Client

$500K capital, age 35, 20-year horizon, moderate-high risk tolerance/moderate capacity, $75K liquidity requirement, 5% crypto max, excludes tobacco/weapons, $2.5M retirement goal. Optimizer might conclude: 50% Global Equities / 25% Bonds / 8% REITs / 5% Gold / 3% Bitcoin / 4% Other Diversifiers / 5% Cash → 79% probability of reaching goal, with stress-test and tax-drag figures attached.

## 47. The Fund Version (detail)

"Multi-Asset Adaptive Wealth Strategy": Global information → AI/NLP research → Economic regime detection → Asset-class scoring → Expected return/risk estimation → Portfolio optimization → Risk constraints → Stress tests → Human investment committee → Execution → Monitoring. The advantage isn't "AI predicts the market" — it's that AI lets a small team process far more information, apply the same framework systematically, and personalize/optimize efficiently.

## 48. Recommended Development Roadmap (original)

1. Research prototype (data ingestion, asset DB, client profile, basic optimizer, risk metrics, Monte Carlo, dashboard — no real money)
2. NLP intelligence (news ingestion, document processing, entity/event extraction, sentiment, source scoring, evidence DB)
3. Client personalization (goal engine, ethical constraints, liquidity constraints, tax engine, personalized optimization)
4. Research validation (backtests, walk-forward, stress tests, out-of-sample, transaction-cost analysis, model comparison)
5. Live paper portfolio (full system live, no external capital, every recommendation tracked)
6. Investment governance (investment committee process, model validation, compliance review, audit trail, risk limits, human approval workflow)
7. Commercial platform (AI investment intelligence software → regulated investment-management operation where appropriate)

*(See Part C for how this maps to what's actually been built so far.)*

## 49. The Most Important Product Differentiator

Not "AI finds investments" (easy to copy). The stronger proposition: **AI constructs a complete, individualized investment decision system around the client's life** — who you are + what you own + what you earn + what you need + what you want to achieve + how much risk you can actually take + what you refuse to invest in + where you pay tax + what the global market is doing → what portfolio has the best probability of helping this specific person achieve their objectives under their constraints.

## 50. Ideal Positioning

> An AI-powered multi-asset wealth intelligence platform that combines real-time information extraction, quantitative portfolio optimization, risk management, tax-aware planning, and personalized financial goals to generate explainable investment strategies.

Not "an AI that tells you what stocks to buy," and not "a chatbot for investing."

## 51. The Ultimate Architecture

```
CLIENT → Client Digital Twin → Goals/Constraints
   → [News, Filings, Markets, Macro, Alternatives] → NLP/LLM Layer
   → Events/Entities/Signals → Quantitative Research
   → Multi-Asset Universe → Opportunity Evaluation
   → [Portfolio Optimizer, Risk Engine, Tax Engine] → Goal Simulation
   → Stress Testing → Recommendation Engine → Explainability
   → Human Oversight → Execution → Portfolio Monitoring
   → back to Client Digital Twin (continuous update loop)
```

## 52. The Big Picture

Three products hidden inside this idea:
- **Product 1 — AI Financial Intelligence:** "What's happening in the world and markets?"
- **Product 2 — AI Portfolio Intelligence:** "What does that mean for my portfolio?"
- **Product 3 — AI Wealth Management:** "Given my entire financial life, what should I do?"

Product 3 is the ambitious end goal; Products 1 and 2 can be built and validated independently — probably the smartest way to approach the project.

**Central design rule:** LLMs interpret information; quantitative models measure it; optimization makes decisions under constraints; risk and compliance constrain those decisions; humans retain oversight.

---

# PART B — TECHNICAL BUILD PLAN

*A concrete stack, with alternatives considered and why each choice wins, for the architecture above. Compiled August 2026.*

## B0. How this differs from Part A

Part A is deliberately vendor-agnostic ("use reliable market data," "a vector database"). This part names actual products, actual libraries, and the reasoning for each choice over its alternatives, plus a punch-list of structural gaps to close before calling the system "robust."

## B1. Refined reference architecture

Two additions to the Part A diagram that are load-bearing, not optional:

- **Point-in-time data layer** (cross-cutting): every price/fundamental/document fact is stamped with `valid_time` (when it was true) and `as_of_time` (when the system knew it), so backtests never accidentally see future-restated data. This must be in the schema from day one — retrofitting it later means replaying your entire history.
- **Model registry / audit log** (cross-cutting): Part A's §22 (source provenance) and §37 (model governance) are really one system. Build it early, not at Stage 6.

## B2. Stack by layer

### B2.1 Core language, API, validation
**Python 3.12** — the entire quant/ML ecosystem (numpy, cvxpy, scikit-learn, statsmodels, PyTorch) is Python-native; splitting the stack adds a serialization boundary you don't need yet.
**FastAPI + Pydantic v2** (over Django/Flask/Node) — native async, and Pydantic models double as the schema layer for both API contracts *and* LLM structured-output validation (see B2.6). One validation library, reused everywhere a number crosses a boundary.

### B2.2 Databases
- **PostgreSQL 16** as system of record (over MongoDB/MySQL) — the schema (clients → goals → recommendations → evidence → documents → model versions) is fundamentally relational; a document store fights the audit-trail joins you need.
- **TimescaleDB** (Postgres extension) for price time series — compression + continuous aggregates without leaving Postgres, avoiding cross-database reconciliation between a price and the recommendation that used it.
- **Redis** for caching and short-lived job queues.
- **pgvector → Qdrant** for document embeddings: start on pgvector (adds nothing to an existing Postgres bill), migrate to Qdrant only once vector volume or filtered-search latency demands it (typically hundreds of thousands to low millions of vectors). Qdrant over Weaviate/Milvus/Pinecone unless hybrid keyword+vector search becomes core — Weaviate's built-in BM25 fusion would then save bolting on Elasticsearch separately.

### B2.3 Point-in-time (bitemporal) data model
`asset_fundamentals(asset_id, metric, value, valid_time, as_of_time, source_id)`. A backtest "as of" a historical date filters `as_of_time <= simulation_date`, guaranteeing it never sees a restatement or correction before it was actually available. The single highest-leverage schema decision in the system, and the most expensive to retrofit.

### B2.4 Market, fundamental, and alternative data — named vendors
| Category | MVP pick | Why | Growth-stage |
|---|---|---|---|
| Equity prices + fundamentals | Financial Modeling Prep or Tiingo | Two most-cited replacements after IEX Cloud's shutdown (Aug 2024); broad coverage, adjusted history, reasonable pricing | Polygon.io / EODHD, then Databento for direct exchange feeds |
| Filings (10-K/10-Q/8-K, XBRL) | SEC EDGAR full-text search + XBRL API | Free, primary-source, satisfies the "prefer primary sources" principle directly | Structured-XBRL vendor once parsed line items are needed at volume |
| Macro/economic data | FRED (St. Louis Fed) | Free, authoritative, the standard for CPI/GDP/rates/employment | World Bank/IMF for non-US coverage |
| Crypto prices | CoinGecko API | Free tier, broad coverage, no exchange quirks | Exchange-native APIs (Kraken, Coinbase) for execution-grade order books |
| News | Small curated set (IR pages, filings, one licensed newswire) | Fewer, higher-credibility sources beat broad scraping for an auditable system | Dedicated licensed newswire API at volume |
| Brokerage/execution | Alpaca (paper trading first) | Purpose-built for the paper-before-real-capital stage | Interactive Brokers API for bonds/international/multi-currency |
| FX | Dedicated FX API or custody provider's feed | Don't derive FX from equity-vendor side channels — usually stale/spread-adjusted | — |

*Note on vendor risk: assume any single vendor can disappear (IEX Cloud — a well-regarded, well-funded provider — shut down its entire data marketplace with roughly three months' notice in 2024). Every category above needs a documented fallback, not just a primary pick.*

### B2.5 NLP / document ingestion
- **`unstructured` / PyMuPDF** for layout-aware parsing across heterogeneous document types.
- **spaCy** (+ finance-tuned model) for cheap high-volume first-pass NER/filtering; **LLM extraction with schema validation** reserved for lower-volume, higher-stakes documents that pass a relevance threshold — running a frontier model over every document is the most common cost mistake here.
- **Microsoft Presidio** for PII detection/redaction — a PDPA-relevant control, not a nicety.
- **MinHash/SimHash** for near-duplicate detection — exact-match dedup misses syndicated wire-service rewrites.

### B2.6 LLM orchestration — making "don't invent numbers" concrete
```
Document → LLM extraction, constrained to a Pydantic schema
   → validation passes → structured event written to DB
   → validation fails → retry with error fed back (max N)
      → still fails → flagged low-confidence, routed to human review (never silently defaulted)
```
Numeric fields the LLM could hallucinate (expected return, growth rate, probability) are **not in the schema at all** — those come only from the deterministic quant layer. The LLM's schema has `sentiment`, its own self-reported `confidence` (logged, never treated as a probability), and free-text rationale — never a number that looks like an investment output.

- **Structured extraction:** Pydantic schemas + validate-and-retry (via `instructor` or hand-rolled) over freeform-parsing-plus-regex — makes the failure mode "extraction rejected" instead of "wrong number silently enters the pipeline."
- **Orchestration:** thin, hand-rolled orchestration for the deterministic research pipeline; a conventional tool-calling loop *only* for the client-facing conversational interface. A heavy agent framework (LangChain/LlamaIndex end-to-end) buys flexibility you don't want in the deterministic half — it's harder to audit and adds a layer between you and the actual API calls.
- **Multi-provider:** thin internal gateway, one interface, swappable backend, with an eval harness run on every model swap so a provider change is a validated config flip, not a rewrite.
- **Cost/latency tiering:** cheap/fast model for bulk classification and first-pass extraction; frontier-tier model reserved for thesis synthesis, contradiction detection, and client-facing explanation. Usually the largest controllable cost at document-ingestion volume.

### B2.7 Portfolio construction / quantitative research
| Component | Recommended | Why |
|---|---|---|
| Classical MVO / Black-Litterman / HRP | **PyPortfolioOpt** | Fastest path to a working optimizer; well-documented, native pandas support |
| Exotic risk measures (CVaR, CDaR, EVaR), tax-aware/goal-based constraints | **Riskfolio-Lib** | Exposes 26 convex risk measures + multiple objective functions, purpose-built for custom constraints (crypto caps, ethical exclusions, liquidity floors) |
| Research-phase walk-forward/cross-validation | **skfolio** | scikit-learn-style `Pipeline`/`cross_val_score` tooling for portfolio models |
| Fully custom objective (the actual utility function from Part A §4: return − λ·risk − γ·drawdown − τ·tax − η·goal-failure) | **cvxpy directly**, on top of the above scaffolding | This multi-term objective doesn't map onto any single library's built-in objective — expect to hand-write it |
| Solver | **CLARABEL** (open-source default) → **MOSEK** (commercial) once robust/CVaR problems at large universes stop converging on free solvers | — |

### B2.8 Backtesting — two different problems
Your actual problem is *quarterly-rebalance, multi-asset, decades-long simulation* — not tick-level order execution.
- **Use:** `vectorbt` (fast vectorized parameter sweeps over allocation/rebalancing rules), `bt` (portfolio-rebalancing-rule backtesting), `empyrical-reloaded` + `quantstats` (performance/risk reporting — don't hand-roll Sharpe/Sortino/VaR formulas).
- **Skip for now:** Backtrader (now in long-term maintenance, not the right 2026 default), Zipline-Reloaded, NautilusTrader, QuantConnect/LEAN — these solve execution realism (order books, slippage, market impact) for frequently-trading strategies. Revisit only if the Fund Version (Part A §31) moves toward active systematic trading.

### B2.9 Monte Carlo / goal simulation
Vectorized numpy/scipy using **block bootstrap of historical returns** or a fitted multivariate Student-t — not naive i.i.d. normal sampling, which understates tail risk and ignores volatility clustering/autocorrelation. `arch` (GARCH family) for volatility-regime stress scenarios.

### B2.10 Risk & performance analytics
`empyrical-reloaded` + `quantstats` — regulatory-grade, well-tested implementations rather than hand-rolled formulas.

### B2.11 Workflow orchestration
**Dagster** over Airflow/Prefect, specifically for this system: Dagster's core abstraction (software-defined assets) maps directly onto "price series / document batch / risk score / recommendation, each with automatic lineage" — which *is* the provenance requirement from Part A §22, largely for free instead of hand-built on a task-based scheduler. Airflow if the team already knows it deeply; Prefect for a very small team wanting minimal ops overhead and not needing asset lineage as a first-class concept.

### B2.12 Infra, security, frontend
- **AWS**, `ap-southeast-1` (Singapore) region for data residency relevant to MAS Technology Risk Management expectations and PDPA.
- **AWS Secrets Manager / Vault** for secrets — never environment-variable secrets for client financial data.
- **Terraform** for IaC — infra changes should be reviewable/versioned like everything else in this system.
- **Docker + ECS/Fargate** for a small team; Kubernetes/EKS only once team and service count justify it.
- **React + TypeScript, Plotly/ECharts/D3** — fine as originally proposed.

## B3. Regulatory reality check (Singapore)

*Framed as engineering-relevant constraints — engage Singapore fintech regulatory counsel to confirm specifics.*

- Digital advisers operate under the existing FAA/SFA framework, clarified by MAS's **Guidelines on Provision of Digital Advisory Services (CMG-G02)**, issued October 2018. Digital advisers offering advisory services generally need an FA licence unless exempted, and can carry out limited SFA-regulated activities incidental to advice (passing orders to a broker, rebalancing) without a separate SFA licence.
- The licence track depends entirely on the operating model: **discretion/control over client money** (fund management, CMS licence) vs. **advice-only with execution passed to a third-party broker**. This determination changes custody architecture and consent flow (per-trade approval vs. discretionary rebalancing) — resolve it *before* building the execution layer, since it changes the `client_accounts`/`transactions` schema.
- CMG-G02 sets algorithm-governance and technology-risk-management expectations, and requires trained staff with relevant expertise to develop and review methodology — this is Part A §37 (model governance) with a named regulatory anchor.
- Firms offering digital fund management to retail investors can be eligible for licensing without the usual track record, provided board/senior management have relevant fund-management and tech experience, the offering is limited to non-complex collective investment schemes, and an **independent audit is completed within the first year of operation** — a concrete roadmap deliverable, not an abstract gesture.
- **PDPA** applies to all client financial data regardless of licensing track — consent, data-residency, breach-notification obligations layer on top of the above.
- MAS runs a regulatory sandbox worth investigating for the paper-trading/Stage-5 phase if testing with a small number of real (not simulated) clients before full licensing.

## B4. Ten robustness gaps to close

1. **Point-in-time data integrity** (B2.3) — build into the schema before the first backtest.
2. **Named fallback vendor per data category** (B2.4) — no single-vendor dependencies.
3. **NLP evaluation harness** — a golden dataset with tracked precision/recall on entity/event extraction, versioned in the same model registry as portfolio models.
4. **LLM cost governance** — explicit model routing by task, with spend tracked per pipeline stage.
5. **Multi-currency consistency layer** — every return/risk/tax calculation resolved to one reporting currency via a single FX-conversion service, or the risk engine, tax engine, and dashboard will quietly disagree.
6. **Idempotent, reproducible recommendation generation** — identical inputs (client profile, market data as-of timestamp, model versions) should produce identical output, or the system logs exactly why it differs.
7. **Circuit breakers on the optimizer** — halt and alert on stale/malformed upstream data rather than silently optimizing over garbage.
8. **A real human-review workflow** — a queue with a diff view (proposed vs. current portfolio + evidence bundle), not just an arrow in a diagram, or the human step degenerates into rubber-stamping.
9. **Adversarial testing of the ethical/ESG screen** — deliberately hard cases (a conglomerate with a small weapons subsidiary; a green-energy company with a legacy fossil-fuel unit) to verify the screen's reasoning, not just its pass/fail output.
10. **Pipeline resilience testing**, distinct from strategy backtesting — vendor rate limits mid-ingestion, partial NLP batch failures, stale feeds during a live session.

## B5. Roadmap → stack mapping

| Stage | Concrete additions |
|---|---|
| 1 — Research prototype | Postgres+TimescaleDB, point-in-time schema, FastAPI, PyPortfolioOpt, numpy Monte Carlo (block bootstrap), FRED+EDGAR+Tiingo/FMP feeds, React dashboard. **Start regulatory-counsel engagement now.** |
| 2 — NLP intelligence | `unstructured`, spaCy first-pass NER, LLM extraction behind Pydantic schemas, pgvector, Dagster ingestion pipelines, NLP evaluation harness |
| 3 — Client personalization | Riskfolio-Lib exotic constraints, tax-rule tables per jurisdiction, ethical-screen logic + adversarial test set |
| 4 — Research validation | skfolio walk-forward, vectorbt + `bt` backtests, `empyrical-reloaded`/`quantstats` reporting, transaction-cost modeling |
| 5 — Live paper portfolio | Alpaca paper mode, optimizer circuit breakers, pipeline resilience tests |
| 6 — Investment governance | Model registry wired to every recommendation, human-review queue UI, MAS licensing determination finalized, independent audit scheduled |
| 7 — Commercial platform | Qdrant migration if warranted, MOSEK evaluation if needed, cost-tiered LLM routing dashboard live |

---

# PART C — CURRENT BUILD STATUS

*This is where the project actually stands. Read this section first if picking up the work.*

## C1. Where this section moved

Part C used to duplicate the repo's implementation status here. That
became a maintenance hazard: this file drifted out of sync with the
actual filesystem once, badly enough that a later session pasted a
`CLAUDE.md` describing files that didn't exist yet and modules marked
"Verified" that had never been run. Never let that happen again.

**`CLAUDE.md` in the repo root is now the single source of truth for
implementation status, the non-negotiable principles, and the
step-by-step plan for what's next.** Read it, not this section, for
"what's actually built." This document (`MASTER_PLAN.md`) stays the
philosophy/rationale reference — Parts A and B above don't change based
on implementation progress, so they're stable to keep here.

As of the most recent session: the full local pipeline (client
profiling with risk-capacity-caps-tolerance, the frontier-positioned
optimizer, a risk engine, stress testing, Monte Carlo goal simulation,
and deterministic explainability) is built, wired together in
`main.py`, and covered by a 12-check test suite that passes. A real
data-vendor integration (Tiingo) is written but unverified — see
`CLAUDE.md` Section 3 for exactly why. Everything from the NLP/LLM
evidence layer downward in the Part A §51 architecture remains
unbuilt; `CLAUDE.md` Section 5 has the ordered plan to get there.
