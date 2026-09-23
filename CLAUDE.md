# CLAUDE.md — Wealth Planning Platform

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
choices with alternatives considered) lives at `MASTER_PLAN.md` in the
repo root. This file is the tighter, engineering-focused companion —
read `MASTER_PLAN.md` for the "why" behind a decision below; read this
file for "what's actually built."

**Project framing:** this is a personal/portfolio engineering project —
a demonstration of the modeling and system design involved in
wealth-management software, not a regulated financial business. There
is no licensing, custody, or compliance layer, and none is planned.
Nothing here produces real investment advice or executes real trades.

---

## 1. What this is

A wealth-planning platform. Given a person's financial circumstances,
goals, constraints, and risk profile, it evaluates a broad multi-asset
universe and constructs a personalized portfolio — evidence-backed and
risk-aware, not a stock-picking chatbot.

The core thesis: **the optimal investment is not universal, it depends
on the investor.** Two people looking at exactly the same market should
get different recommendations. A 28-year-old with a long horizon and
high risk tolerance and a 57-year-old retiring in seven years should
never land on the same portfolio just because they asked the same
system on the same day. Every architectural decision below serves that
thesis — the client profile is a first-class input into optimization,
not a label applied after the fact.

The second design rule, equally load-bearing: **LLMs interpret
information; quantitative models measure it; optimization makes
decisions under constraints; humans retain oversight.** Nothing is
allowed to output a number that reaches a client directly without
passing through a real model. `evidence.py` (the NLP layer skeleton)
produces sentiment and event tags, never a return, a price target, or a
probability — see Section 4, Principle 1.

---

## 2. How it's supposed to work — the full pipeline

```
Client Profile (age, goals, risk tolerance/capacity, liquidity,             [BUILT]
                tax jurisdiction, ethical exclusions)
        │
        ▼
Effective Risk Score (risk capacity CAPS risk tolerance)                    [BUILT]
        │
        ▼
Investment Universe (22 instruments across Equity, Bonds, Commodities,      [BUILT]
        │             Real Estate -- listed and direct, Private Markets --
        │             equity and credit, Crypto, Cash. See universe.py.)
        ▼
Constraints (crypto cap, illiquidity cap, per-position concentration        [BUILT]
        │     cap, ethical sector exclusions, cash floor -- all generic
        │     ticker-group mechanics, see portfolio_optimizer.Constraints)
        ▼
Portfolio Optimizer (positions the client at the point on the efficient     [BUILT]
        │             frontier matching their risk score, using return
        │             estimates shrunk toward a house-view prior rather
        │             than raw historical means -- see Section 4 §7)
        ▼
Risk Engine (Sharpe, Sortino, max drawdown, VaR/CVaR on the chosen          [BUILT]
        │    portfolio's own realized return series)
        ▼
Stress Testing (six scenarios, shocked at the asset-class level)            [BUILT]
        ▼
Tax Drag (jurisdiction-configurable income + realized-gains tax             [BUILT]
        │  estimate, reducing gross to net expected return)
        ▼
Goal Simulation (Monte Carlo, Student-t fat tails, on the net-of-tax        [BUILT]
        │         return -- probability of reaching a stated goal)
        ▼
Explainability (plain-English rationale, generated deterministically       [BUILT]
        │        from the numbers already computed above -- no LLM call)
        ▼
NLP/LLM Evidence Layer (schema-validated sentiment/event extraction,        [BUILT,
        │               rule-based lexicon extractor by default --         NOT WIRED
        │               produces Evidence records but nothing downstream   INTO THE
        │               consumes them yet. See Section 4 §8.)              OPTIMIZER]
        ▼
Human Investment Review (a queue table + approve/reject workflow with      [BUILT]
        │                 a proposed-vs-previous weights diff. No
        │                 execution endpoint exists anywhere to bypass.)
        ▼
Execution & Monitoring                                                      [NOT BUILT,
                                                                              NOT PLANNED]
```

**Why this order, not some other order:** the risk score has to exist
before optimization (it's the input, not a post-hoc label); risk/stress/
tax/goal analysis has to happen on the *actual chosen* portfolio, not a
generic one, which is why they come after the optimizer, not before;
explainability comes last because it explains real computed numbers.

---

## 3. Current repo state — what's actually real

Be precise here. "Written" and "verified" are different claims. All
`.py` files below were implemented and run in this session (2026-09-23);
`test_pipeline.py` (17 checks) and `test_api.py` (13 checks) both pass,
`main.py` runs cleanly end to end, and the API was confirmed both via
FastAPI's `TestClient` and booting under a real `uvicorn` process.

| File | Status |
|---|---|
| `universe.py` | **Verified.** 22 instruments across Equity (8, including sector-tagged ones for exclusion testing), Bonds (4), Commodities (3), Real Estate (2 -- listed REITs and unlisted direct real estate), Private Markets (2 -- private equity and private credit), Crypto (2), Cash. Returns generated from a 6-factor statistical model (Equity/Rates/Credit/Commodity/Crypto/RealAsset), with the factor correlation matrix checked for positive-semidefiniteness at import time. Private equity, private credit, and direct real estate get an AR(1) appraisal-smoothing pass on top (Geltner-style), which is *why* their reported volatility comes out well below their target volatility in a test run -- confirmed deliberately, not a bug (see the module docstring). |
| `estimators.py` | **Verified.** James-Stein-style shrinkage of expected returns, generalized to shrink toward an external prior (defaults to the cross-sectional grand mean if none given) rather than plain historical means. Shrinkage intensity is capped at 90%, not 100% -- full shrinkage makes every asset's expected return identical, which leaves "highest-return portfolio" undefined. Confirmed this cap binds often even at 20 years of simulated daily history for a 22-asset universe, which is itself a real, well-known result (distinguishing expected returns from price noise takes far more data than most people assume), not a parameter-tuning artifact. |
| `house_view.py` | **Verified.** The shrinkage prior: one illustrative long-run return assumption per asset class (the kind every wealth manager publishes annually), deliberately *not* derived from `universe.py`'s own generating parameters -- if it were, the shrinkage would just be recovering the answer key instead of doing real estimation work. |
| `data_vendor.py` | **Written, NOT verified.** Real Tiingo (equities/ETFs/bonds/commodities/REITs, via each instrument's `real_ticker`) + CoinGecko (crypto, no key required) integration. Never executed against either live API: this sandbox's egress policy rejects outbound connections to every external host tested, Tiingo and CoinGecko included (confirmed via direct `curl`, independent of holding an API key). See Section 5 Step 1 and the vendor connect guide below for what running this for real actually takes. |
| `data_source.py` | **Verified for the synthetic path only.** Single `USE_REAL_DATA` switch point used by both `main.py` and `api.py`. The real-data branch inherits `data_vendor.py`'s unverified status. |
| `client_profile.py` | **Verified.** `ClientProfile`/`Goal` dataclasses; `effective_risk_score` implements capacity-caps-tolerance (checked explicitly, including that it's *not* the average of the two); `crypto_cap`, `illiquid_cap`, `min_cash`, `excluded_sectors`, `tax_jurisdiction` all flow through to the optimizer and tax estimator. |
| `portfolio_optimizer.py` | **Verified.** `Constraints` dataclass expresses crypto cap, illiquidity cap, ethical exclusions, cash floor, and a per-position concentration cap (default 30%, cash exempt) all as generic named ticker-groups-with-a-cap -- the module itself doesn't know what "crypto" means, `universe.py` and the caller decide the groupings. `risk_tolerance` maps to a target point on the frontier via the min-vol/max-feasible-return endpoints, with a defensive fallback chain (max-Sharpe, then min-vol) for the case where heavy shrinkage makes "highest return" nearly undefined -- this edge case was hit and fixed during this session, not theoretical. |
| `risk_engine.py` | **Verified.** Sharpe/Sortino/drawdown/VaR/CVaR, computed directly on the portfolio's own realized return series. |
| `tax.py` | **Verified.** Five illustrative jurisdiction profiles (`none`, `us_taxable`, `uk`, `singapore`, `india`) -- flat, simplified rates standing in for real bracketed/situational rules, explicitly labeled as such, not tax advice. Drag = tax on income received (per-instrument `income_yield` in `universe.py`, routed to a dividend or interest rate depending on asset class) + tax on gains actually realized through assumed rebalancing turnover, at a short- or long-term rate depending on assumed holding period. Confirmed Singapore's profile matches the zero-tax baseline, matching how Singapore actually treats individual investors. |
| `stress_test.py` | **Verified.** Six scenarios (added a Liquidity Crunch scenario alongside the original five), shocks applied per asset class via `universe.ASSET_CLASS_OF` rather than hardcoded ticker names -- necessary once the universe grew past a handful of instruments. Magnitudes are illustrative, not calibrated to specific historical analogues yet. |
| `goal_simulator.py` | **Verified.** Monte Carlo with a Student-t (fat-tailed) shock distribution, deliberately not i.i.d. normal; now fed the *net-of-tax* expected return from `tax.py`, not the gross optimizer output. |
| `explainability.py` | **Verified.** Rule-based templating only -- deliberately not an LLM call. Now also narrates the tax-drag line when nonzero, and uses human-readable instrument names via `universe.py` instead of raw tickers. |
| `evidence.py` | **Verified, NOT wired into the optimizer.** `Evidence` schema deliberately has no numeric investment fields (no expected_return, no price_target, no probability) -- only entity, event_type, sentiment, confidence, source, timestamp, summary. Default extractor is a small hand-built positive/negative keyword lexicon (the same basic idea as the Loughran-McDonald financial sentiment word lists used as a standard NLP-in-finance baseline), needs no API key, runs offline. `validate_evidence()` enforces the schema and rejects out-of-range values -- the same contract a real LLM-backed extractor would need to satisfy, so one can be dropped in later behind the same interface. Not yet connected to opportunity scoring or the optimizer in any way; it's a parallel, additive capability today. |
| `db.py` | **Verified.** Plain `sqlite3`. Tables: `clients`, `goals`, `recommendations` (weights/risk-metrics/stress-results/goal-result/tax-result as JSON, plus three separate version fields -- `code_version` from git, `data_version` from `data_source`, `model_version` from `version.py`, kept separate on purpose, see that file's docstring), `review_queue` (proposed vs. previous-approved weights, status, reviewer note). |
| `version.py` | **Verified.** `MODEL_VERSION`, bumped only when the optimization methodology itself changes (a new estimator, a changed constraint set) -- not on every commit, unlike `code_version`. |
| `api.py` | **Verified.** FastAPI: client CRUD-lite, `POST .../recommendations` (runs the full pipeline and persists it), `POST /recommendations/{id}/submit-for-review`, `GET /reviews`, `GET /reviews/{id}`, `POST /reviews/{id}/decide`, `GET /health`. No execution endpoint exists anywhere, and there is a real (if minimal) review workflow now, not just an architectural promise. |
| `test_pipeline.py` | **Verified.** 17 checks: constraint satisfaction (crypto/illiquid/concentration caps, ethical exclusions, cash floor) across the full risk-tolerance range, frontier monotonicity, capacity-caps-tolerance, VaR/CVaR ordering, tax drag behavior including the Singapore zero-tax case, evidence schema validation, goal-probability bounds, full end-to-end run with exclusions. All pass. |
| `test_api.py` | **Verified.** 13 checks, including ethical exclusions and tax jurisdiction applied through the live API (not just `main.py`), and the review-queue workflow (submit, list pending, decide, `previous_weights` correctly carrying forward from the last *approved* recommendation on the next submission). All pass. |
| `main.py` | **Verified.** Two example clients through the full pipeline, both now with real goals, exclusions (Client B), and different tax jurisdictions -- prints gross and net-of-tax return, risk metrics, six stress scenarios, goal probability, and the explanation. |
| `export_frontier.py` / `wealth_demo_template.html` → `wealth_demo.html` | **Verified.** Precomputes a 41-point risk-tolerance grid across the full 22-instrument universe and embeds it in a self-contained, slider-driven static page (human-readable instrument names and asset-class labels, no server, no CDN dependency). Not wired to call the live API -- still reads its own precomputed grid. |

**Not started at all:** persistent connection between `evidence.py`'s
output and anything that acts on it (opportunity scoring, the
optimizer, or even just attaching evidence to a stored recommendation),
a frontend beyond the static demo, backtesting/walk-forward validation,
point-in-time data integrity, individual-security-level fundamental
data (the universe is 22 representative instruments, not thousands of
underlying names), and anything that turns a recommendation into a
trade.

---

## 4. Non-negotiable principles

1. **No LLM-invented numbers.** `evidence.py` produces sentiment, event
   tags, and a self-reported confidence score -- never a return,
   volatility, or probability that reaches a client without passing
   through a real quantitative model first.
2. **Risk capacity caps risk tolerance**, not an average of the two.
   `ClientProfile.effective_risk_score` encodes this; there's a
   dedicated test for exactly this property.
3. **The client stays a first-class input.** If a change makes two
   differently-profiled clients start converging toward the same
   output by default, that's a regression, not a simplification.
4. **Honest labeling, always.** Synthetic vs. real data, tested vs.
   untested code, illustrative vs. calibrated assumptions -- called out
   explicitly, never silently presented as more mature than they are.
   This file previously drifted badly out of sync with the actual repo
   (claiming files existed that hadn't been written); if that ever
   happens again, fix the doc against the filesystem, not the reverse.
5. **Tests stay green, and grow with the code.** Every new module gets
   tests that check properties (constraint satisfaction, boundedness,
   monotonicity), not just "it ran."
6. **Human review before execution**, once there's anything to
   execute. `review_queue` exists specifically so this workflow is
   already in the codebase before there's ever a reason to skip
   building it. No API endpoint lets a recommendation become a trade —
   not even behind a flag.
7. **Shrink expected returns toward an independent prior, not toward
   the sample itself.** Plain James-Stein shrinkage toward the
   cross-sectional grand mean still inherits some of the noise it's
   trying to correct for, especially when one or two extreme assets
   (crypto, in this universe) can drag the grand mean around. Shrinking
   toward `house_view.py`'s stated capital-market assumptions instead
   keeps the correction anchored to something genuinely independent of
   the noisy sample -- don't quietly revert this to plain grand-mean
   shrinkage for convenience.
8. **No code, comments, or docs in this repo should read as
   AI-generated or mention the tooling used to build it.** Write
   everything as a human engineer's own notes and commits.

---

## 5. Step-by-step plan for what's next

**Step 1 — Verify real data. BLOCKED IN THIS SANDBOX, not blocked in general.**
This environment's egress policy rejects every external host tested
(Tiingo, CoinGecko, and several other data vendors all returned a
403 on the CONNECT itself). None of that is fixable from in here.
Outside this sandbox: get a free Tiingo API key (see the connect guide
below), run `data_vendor.py` standalone, confirm its output matches
`universe.generate_universe_prices()`'s shape, then
`USE_REAL_DATA=1 python3 main.py`. Expect some numbers to shift once
real history replaces the synthetic generator -- that's expected.

**Step 2 — Wire evidence into something.** `evidence.py` produces
records that nothing downstream reads yet. The honest next move,
consistent with Principle 1, is *not* to feed sentiment into the
optimizer's return estimate directly -- it's to attach evidence records
to a stored recommendation as supporting/contradicting context (a
`recommendation_evidence` table, evidence surfaced alongside the
explanation) so a human reviewer sees it, without it ever becoming a
number the optimizer consumes.

**Step 3 — A frontend against the live API.** `wealth_demo.html` still
reads its own precomputed grid; pointing it (or a proper small
frontend) at `api.py` would make the whole thing feel like a real
product rather than a script plus a static demo.

**Step 4 — Backtesting / walk-forward validation.** Nothing in this
repo has been tested against out-of-sample performance yet. Worth
doing before trusting the shrinkage-toward-house-view estimator (or any
future estimator) beyond a demo context.

**Step 5 — Calibrate the stress scenarios.** Current shock magnitudes
in `stress_test.py` are illustrative. Calibrating them against actual
historical analogues (GFC, COVID, a real rate-hike cycle) would make
the numbers defensible rather than just plausible-looking.

**Step 6 — Point-in-time data integrity**, if real data ever gets
wired in for real: every price/fundamental fact needs a `valid_time`/
`as_of_time` pair so a later backtest can't accidentally see
restated data. Cheap to add now, expensive to retrofit.

---

## 6. Connecting real data (outside this sandbox)

Two vendors, matched to what each is actually good for. Both are free
at the scale this project needs.

**Tiingo** — equities, ETFs, bond funds, REITs, commodity funds (every
instrument in `universe.py` with a `real_ticker` set, except the two
crypto instruments):
1. Sign up at tiingo.com (free tier is enough for this).
2. Generate an API key from the account settings page.
3. `export TIINGO_API_KEY=your_key_here` (or put it in a local `.env`
   you don't commit).
4. `python3 data_vendor.py` on its own first, to sanity-check the
   output before trusting it anywhere downstream.

**CoinGecko** — Bitcoin and Ethereum. No signup, no key, for the basic
`market_chart/range` endpoint this project uses. If CoinGecko's free
tier ever starts rate-limiting a real workload, they do offer a paid
Demo/Pro API key that raises the limit; not needed to get started.

Once both check out standalone, `USE_REAL_DATA=1 python3 main.py`
routes everything through `data_source.get_prices()` into the real
data path instead of the synthetic generator -- no other code changes
needed, by design (see `data_source.py`'s docstring).

---

## 7. Your call — deliberately unspecified

- Exact API route naming/versioning scheme
- Database library choice beyond raw `sqlite3`, if it ever needs to change
- Code organization into packages/modules beyond the current flat layout
- Frontend/charting choices for anything beyond the existing static demo
- Which LLM provider/model if `evidence.py` ever gets a model-backed
  extractor alongside the lexicon one, as long as it goes through the
  same schema-validated, no-numbers `Evidence` contract
- Whether to migrate the plain-assert test runners to pytest
- Naming conventions beyond what's already established in the existing files
