# CLAUDE.md — AI-Powered Multi-Asset Wealth Management Platform

## Read this first

This file is project context, read automatically at the start of every
Claude Code session in this repo. It exists so the project doesn't need
re-explaining each time. Three kinds of content live here, marked
differently on purpose:

- **Vision & architecture** — why this exists and how it's meant to fit
  together. Stable; shouldn't change casually.
- **Non-negotiable principles** — specific constraints that must survive
  any refactor, no matter how the implementation evolves.
- **Your call** — implementation details deliberately left open. Pick
  whatever's idiomatic. Don't ask permission for these; just decide and
  move on, and use good judgement on things not covered here either.

If a plan below turns out to be wrong once you're actually in the code,
say so and propose the fix — this document is a starting point for a
session, not a contract to follow past the point it stops making sense.

The full philosophy/rationale document (product vision, technical stack
choices with alternatives considered, Singapore regulatory framework)
lives at `MASTER_PLAN.md` in the repo root. This file is the tighter,
engineering-focused companion — read `MASTER_PLAN.md` for the "why"
behind a decision below; read this file for "what's actually built."

---

## 1. What this is

An AI-powered wealth-management and investment-intelligence platform.
It evaluates a client's financial circumstances, goals, constraints,
risk profile, and tax situation, then constructs a personalized
multi-asset portfolio — evidence-backed and risk-aware, not a
stock-picking chatbot.

The core thesis: **the optimal investment is not universal, it depends
on the investor.** Two clients looking at exactly the same market
should get different recommendations. A 28-year-old with a long
horizon and high risk tolerance and a 57-year-old retiring in seven
years should never land on the same portfolio just because they asked
the same system on the same day. Every architectural decision below
serves that thesis — the client profile is a first-class input into
optimization, not a label applied after the fact.

The second design rule, equally load-bearing: **LLMs interpret
information; quantitative models measure it; optimization makes
decisions under constraints; humans retain oversight.** An LLM is never
allowed to output a number that reaches a client directly. If a future
session is tempted to let an LLM produce "expected return: 9%" or
similar, that's the point to stop and route it through a real model
instead. Nothing in this repo currently calls an LLM at all — that's
correct for where the build is (see Section 3).

---

## 2. How it's supposed to work — the full pipeline

This is the target architecture. Sections below mark what's built vs.
not yet.

```
Client Profile (age, goals, risk tolerance/capacity, liquidity,
                tax jurisdiction, ethical constraints)                    [BUILT]
        │
        ▼
Effective Risk Score (risk capacity CAPS risk tolerance — a client       [BUILT]
        │             can't be pushed past what their situation can
        │             actually absorb, regardless of stated comfort)
        ▼
Investment Universe (currently: 6 broad asset classes. Target:          [PARTIAL]
        │             individual securities within each class, which
        │             is what makes ethical/ESG screening meaningful)
        ▼
Portfolio Optimizer (positions the client at the point on the           [BUILT]
        │             efficient frontier matching their risk score —
        │             NOT always the max-Sharpe portfolio. Two clients
        │             with different scores get different portfolios,
        │             which is the whole point)
        ▼
Risk Engine (Sharpe, Sortino, max drawdown, VaR/CVaR — computed on the   [BUILT]
        │    chosen portfolio's own realized return series, not assumed)
        ▼
Stress Testing (scenario shocks — equity crash, rate shock, inflation,  [BUILT]
        │        recession, crypto crash — applied to the actual weights)
        ▼
Goal Simulation (Monte Carlo, fat-tailed distribution — probability of  [BUILT]
        │         reaching a stated goal, not a single-point forecast)
        ▼
Explainability (plain-English rationale, generated deterministically    [BUILT]
        │        from the numbers already computed above — no LLM call,
        │        nothing here is a new estimate)
        │
        │  ┌─── NOT YET BUILT, target architecture from here down ───┐
        ▼  ▼
NLP/LLM Evidence Layer (turns news/filings into structured, schema-
        │               validated evidence that feeds opportunity
        │               scoring BEFORE optimization — never a number
        │               injected directly into the pipeline)
        ▼
Human Investment Review (a queue with a diff view — proposed vs.
        │                 current portfolio, plus the evidence bundle.
        │                 Not optional, not a rubber stamp)
        ▼
Execution & Monitoring (continuous re-evaluation as markets and client
                         circumstances change)
```

**Why this order, not some other order:** the risk score has to exist
before optimization (it's the input, not a post-hoc label); risk/stress/
goal analysis has to happen on the *actual chosen* portfolio, not a
generic one, which is why they come after the optimizer, not before;
explainability comes last because it explains real computed numbers —
it would be backwards (and dishonest) for it to generate prose that
the numbers are then bent to match.

---

## 3. Current repo state — what's actually real

Be precise here. "Written" and "verified" are different claims.
Everything below was implemented and run in this session, most
recently on 2026-09-23; `test_pipeline.py` (12 checks), `test_api.py`
(9 checks), and `main.py` all pass/run cleanly as of that commit, and
the API was additionally confirmed booting under a real `uvicorn`
server and answering real HTTP requests via `curl` — not just
FastAPI's in-process `TestClient`.

| File | Status |
|---|---|
| `synthetic_data.py` | **Verified.** Placeholder multi-asset price generator. Every downstream module only depends on a DataFrame of prices — swapping the source changes nothing else. |
| `data_vendor.py` | **Written, NOT verified.** Real Tiingo integration, follows the documented API shape. Never successfully executed against the live API: this environment's egress proxy rejects connections to `api.tiingo.com` outright (organization policy — confirmed via a direct `curl`, independent of having an API key), so it couldn't even be smoke-tested here. Run it yourself, outside this sandbox, with a real `TIINGO_API_KEY`, and confirm the output shape matches `synthetic_data.py`'s before trusting it anywhere. |
| `data_source.py` | **Verified for the synthetic path only.** Single switch point (`get_prices()`, gated by `USE_REAL_DATA=1`) used by both `main.py` and `api.py` so they don't each reimplement the branch. The synthetic branch is exercised by every test in the repo. The real-data branch inherits `data_vendor.py`'s unverified status above — flipping the flag is wired but untested. |
| `client_profile.py` | **Verified.** `ClientProfile`/`Goal` dataclasses; `effective_risk_score` implements capacity-caps-tolerance, checked explicitly in `test_pipeline.py` (not just capacity-caps-tolerance, but that it's *not* the average of the two). |
| `portfolio_optimizer.py` | **Verified**, including the target-return-ceiling issue: the max-feasible-return endpoint is found via a bounded search over `efficient_return()` (`_max_feasible_return`) rather than naively using `mu.max()`, so the crypto-cap/cash-floor constraints are respected even at `risk_tolerance=1.0`. Confirmed by test: crypto cap and cash floor both hold across the full 0–1 risk-tolerance range. |
| `risk_engine.py` | **Verified.** Sharpe/Sortino/drawdown/VaR/CVaR, computed directly, not via a library — small enough set of formulas that a direct implementation is easier to audit than a dependency. |
| `goal_simulator.py` | **Verified.** Monte Carlo with a Student-t (fat-tailed) shock distribution, deliberately not i.i.d. normal; variance rescaled so volatility matches the requested input regardless of degrees of freedom. |
| `stress_test.py` | **Verified.** Five illustrative scenarios. Shock magnitudes are illustrative, not calibrated to historical analogues yet (see Step 6 below). |
| `explainability.py` | **Verified.** Rule-based templating only — deliberately not an LLM call (see Section 1). |
| `db.py` | **Verified.** Plain `sqlite3`, not an ORM. Schema: `clients`, `goals`, `recommendations` (weights/risk-metrics/stress-results/goal-result as JSON columns, plus `code_version` — real git short SHA, pulled via `git rev-parse --short HEAD` — and `data_version` audit fields). Client save/fetch and recommendation save/fetch/list all round-tripped correctly in a smoke test against a temp file DB before `api.py` was built on top of it. |
| `api.py` | **Verified.** FastAPI app: `POST /clients`, `GET /clients/{id}`, `POST /clients/{id}/recommendations` (runs the full pipeline and persists it), `GET /clients/{id}/recommendations`, `GET /recommendations/{id}`, `GET /health`. Deliberately has no execution endpoint — see Principle 6. Confirmed working both via `TestClient` and via a real `uvicorn` process hit with `curl`. |
| `test_pipeline.py` | **Verified.** 12 checks on properties that matter (weights sum to 1, crypto cap/cash floor hold at every risk tolerance, frontier is monotonic non-decreasing in return, risk capacity caps rather than averages tolerance, VaR/CVaR ordering, goal probabilities bounded 0–1, full pipeline runs end-to-end) rather than just "did it execute." All 12 pass. Keep this green; extend it for every new module. |
| `test_api.py` | **Verified.** 9 checks against the API using an isolated temp SQLite DB per check (health, client creation/validation including a 422 on an out-of-range `risk_tolerance`, 404s on unknown ids, recommendation persistence round-trip, list growth across repeated requests, and that two differently-profiled clients get different volatility through the live API, not just through `main.py`). All 9 pass. |
| `main.py` | **Verified.** Runs two example clients (mirroring the original "Client A"/"Client B" personas, now with actual `Goal`s) through the full built pipeline via `data_source.get_prices()` and prints a report including risk metrics, stress results, goal probability, and the generated explanation. |
| `export_frontier.py` / `wealth_demo_template.html` → `wealth_demo.html` | **Verified.** `export_frontier.py` precomputes a 41-point risk-tolerance grid (weights/return/vol/Sharpe at each point) in Python and writes it into a self-contained static HTML page (`wealth_demo.html`, generated — not committed as a separate source artifact, regenerate via `python3 export_frontier.py`). The page is a plain SVG chart + slider with no server and no CDN dependency, so it opens directly from a local `file://` path. Confirmed the embedded JSON is well-formed and the placeholder markers are fully substituted. Not yet wired to call the live API — it still reads its own precomputed grid, not `api.py`. |

**Not started at all:** individual-security universe (still 6 broad
asset classes), ethical/ESG screening (not meaningful yet at
asset-class granularity — `ClientProfile.excluded_sectors` exists as a
field and flows into the explanation text, but nothing actually filters
the universe by it yet), the NLP/LLM evidence layer, tax modeling, a
*formalized* model registry (recommendations already carry
`code_version`/`data_version`, but nothing versions the optimizer
config or risk model separately yet — see Step 9), a human-review UI
(the principle is upheld today only by there being no execution
endpoint at all — see Step 8), and anything regulatory.

---

## 4. Non-negotiable principles

These should survive any refactor, regardless of how the "your call"
items get decided:

1. **No LLM-invented numbers.** Any future LLM integration produces
   evidence, tags, sentiment, or prose — never a return, volatility, or
   probability that reaches a client without passing through a real
   quantitative model first.
2. **Risk capacity caps risk tolerance**, not an average of the two.
   `ClientProfile.effective_risk_score` encodes this; don't flatten it
   to a simple mean in some future refactor for convenience. There is a
   dedicated test for this exact property — don't let it regress.
3. **The client stays a first-class input.** If a change makes two
   differently-profiled clients start converging toward the same
   output by default, that's a regression, not a simplification.
4. **Honest labeling, always.** Synthetic vs. real data, and
   tested vs. untested code, get called out explicitly in comments and
   docs — never silently presented as more mature than they are. This
   file itself follows that rule (see Section 3) — it was previously
   found to be badly out of sync with the actual repo (claiming files
   existed that hadn't been written yet); if that ever happens again,
   fix the doc against the actual filesystem state, not the reverse.
5. **Tests stay green, and grow with the code.** `test_pipeline.py`
   caught a real constraint-violation bug during development. Every new
   module gets tests that check properties, not just "it ran" — see the
   existing tests for the pattern (constraint satisfaction, boundedness,
   monotonicity).
6. **Human review before execution**, once there's anything to execute.
   No API endpoint should let a recommendation become a trade without
   that step existing first — not even for a demo, not even behind a
   flag.

---

## 5. Step-by-step plan for what's next

Ordered by dependency — each step assumes the previous ones are done.
Pick up wherever fits the available time; each step should leave the
repo in a working, tested state, not a half-finished one.

**Step 1 — Verify real data. PARTIALLY DONE.**
`data_source.py` now has the `USE_REAL_DATA` env-var switch, and both
`main.py` and `api.py` go through it rather than importing
`synthetic_data` directly. What's left: get a free Tiingo API key and
run `data_vendor.py` *outside this sandbox* (its egress policy blocks
`api.tiingo.com` outright, so this cannot be completed inside the
current environment — confirm whatever environment attempts it next
actually has real network access first). Confirm its output DataFrame
matches `synthetic_data.py`'s shape (same columns, sane price levels),
then actually run `USE_REAL_DATA=1 python3 main.py` and `test_pipeline.py`
end to end. Expect some numeric assumptions to shift once real
historical returns replace the synthetic assumptions; that's expected,
not a bug to paper over by loosening test tolerances without thinking
about why.

**Step 2 — Persistent storage. DONE.**
`db.py`, plain `sqlite3` (not Postgres+TimescaleDB — that heavier stack
earns its complexity later, not on day one of a solo build). Clients,
goals, and recommendations (weights + risk/stress/goal-simulation
results as JSON, plus `code_version`/`data_version` audit fields) all
persist and round-trip. This is the seed of the model-registry
principle (Step 9), not the full thing yet — it records *what* produced
a recommendation, not a separately versioned config for the optimizer
or risk model.

**Step 3 — API layer. DONE.**
`api.py`, FastAPI. Create a client, request a recommendation (runs the
full pipeline and persists it), fetch a client or a past recommendation
back. Verified both via `TestClient` and via a real `uvicorn` process
hit with `curl` (see Section 3). `wealth_demo.html` is not yet wired to
call this live — it still reads its own precomputed grid from
`export_frontier.py`. Pointing the demo at the live API (or building a
small new frontend against it) is reasonable next-session scope, but
wasn't done here since the existing demo already satisfies "a UI could
call this."

**Step 4 — Expand the investment universe.**
Move from 6 broad asset classes to real constituent securities, at
least within the equity sleeve (a basket of real stocks/ETFs). This is
what makes the next two steps meaningful rather than token.

**Step 5 — Ethical/exclusion screening.**
Simple rule-based sector/company exclusion (tobacco, weapons, gambling,
fossil fuels) against the expanded universe. `ClientProfile.excluded_sectors`
already exists as a field (currently decorative — it shows up in the
explanation text but doesn't filter anything); this step is what makes
it real. Not a full controversy classifier yet — that's downstream of
Step 6.

**Step 6 — First NLP/LLM evidence layer.**
Small, curated source list to start (e.g. SEC EDGAR filings for
whatever's in the universe after Step 4). Schema-validated extraction
— a Pydantic schema with no numeric investment fields, a retry-on-
validation-failure loop, low-confidence extractions routed to a review
queue rather than silently dropped or guessed. This is where Principle
1 in Section 4 gets its first real test.

**Step 7 — Tax-drag estimation, one jurisdiction.**
Singapore, since that's what's already been scoped conceptually.
Simplified capital-gains and dividend-withholding treatment — not
comprehensive, just enough to show up in a recommendation's numbers.

**Step 8 — Human-review workflow.**
Even a minimal version — a queue table plus a simple diff view (proposed
vs. current portfolio, with the evidence bundle attached) — beats not
having one. This is what keeps Principle 6 real instead of aspirational
once Step 3's API makes it possible to bypass.

**Step 9 — Model registry, formalized.**
Version the optimizer config, the risk model, and any LLM prompts;
link every stored recommendation to the exact versions that produced
it.

**Step 10 — Regulatory/licensing.**
Not a coding task. Runs in parallel with actual counsel, not as a
"later" item on this list to eventually write code for.

---

## 6. Your call — deliberately unspecified

Don't treat these as open questions to bring back for discussion;
decide and proceed:

- Exact API route naming/versioning scheme
- Database library choice (raw `sqlite3`, SQLAlchemy, SQLModel — whatever)
- Code organization into packages/modules beyond the current flat layout
- Frontend/charting choices for anything beyond the existing static demo
- Which LLM provider/model for Step 6, as long as it goes through the
  schema-validated, no-numbers pattern
- Whether to migrate `test_pipeline.py`'s plain asserts to pytest
- Naming conventions beyond what's already established in the existing files
