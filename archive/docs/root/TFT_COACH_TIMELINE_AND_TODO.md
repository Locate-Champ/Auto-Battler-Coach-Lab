# TFT Coach Upgrade: Timeline + Extremely Detailed To‑Do (Codex Handoff)

Last updated: 2026-02-13  
Owner: Codex (implementation), Forrest (product decisions + review)

## Why this plan exists

The repo already has:
- A deterministic Set 16 full-game simulator that emits **decision-time snapshots** (per alive player, per PvP round) and writes Parquet/JSONL chunks.
- A working live runtime loop (logs/Redux → state → WebSocket → coach → UI).
- A simulator-trained ML pipeline (`models/`) with XGBoost baselines and a cross-attention transformer.
- A coaching layer (`coach/`) that is conceptually “planning with a critic” but can be made more rigorous, more explainable, and easier to extend.

This plan turns the coach into a consistently structured “planner + critic” system:
1) generate a small set of legal candidate actions  
2) deterministically apply each action → next-state(s)  
3) score next-states using a mix of:
   - **combat simulation** (tempo / immediate strength)
   - **learned evaluator** (fast proxy for board quality + matchup odds)
   - **archetype prior** (coherence / “where this board is going”)
   - **econ math** (interest, level timing, HP risk)
4) return the top actions + *numbers* + *reasons* (with confidence buckets)

We explicitly avoid the fragile route of “learn a decision policy from final snapshots via IPS-weighted contextual bandits.” With the simulator, we can get decision-time labels and counterfactuals in a much cleaner way.

---

## Non-goals (keep Codex from overbuilding)

- Do **not** build a monolithic RL agent.
- Do **not** assume scraped human match finals can directly supervise decision-time actions.
- Do **not** ship “absolute winrate” claims without confidence and/or simulator support.
- Do **not** let modules invent their own state representations or legality rules.

---

## Global deliverables (what “done” looks like overall)

### Runtime (live coach)
- A stable `Coach.recommend(...)` pipeline that produces:
  - top 1–3 recommendations per decision type (items/position/econ/shop)
  - per-recommendation score breakdown
  - an explanation payload designed for UI display
  - confidence buckets (high / medium / coin_flip / low)
- Deterministic action execution (given the same input state + seeds, outputs are repeatable).
- Combat scoring with:
  - caching
  - consistent seed usage for comparisons
  - adaptive sim budgets (coarse → refine)

### Offline artifacts
- An **archetype library artifact** (clustered comps + summaries) loadable by runtime coach.
- A **runtime evaluator artifact** (XGBoost or transformer) loadable by runtime coach.
- Reproducible experiment manifests for baselines and future training runs.

### Docs & contracts
- Versioned schema docs for:
  - LiveState → CoachState conversion contract
  - SnapshotRow schema (collector output)
  - Explanation payload schema (coach → WS → UI)
  - Model artifact schema (how runtime loads models)
  - Feature/encoder versioning

### Tests
- Unit tests for:
  - legality rules
  - deterministic executors
  - encoding stability
  - combat scoring determinism (seeded)
- Integration tests for:
  - `app/server/websocket.py` conversion + coach call
  - “candidate→execute→score” returns sensible payloads
- Regression tests for:
  - schema compatibility
  - performance budgets (avoid accidental N× explosions)

---

## Implementation timeline (ordered milestones, no calendar guessing)

Each milestone has:
- ✅ To‑do checklist (Codex implements)
- 📦 Artifacts produced
- 🧪 Acceptance tests / validation gates

You can implement milestones sequentially; later milestones assume earlier contracts exist.

---

# Milestone 0 — Baseline freeze + repo truth table

Goal: make sure everyone (Codex + future-you) can answer “what’s running where” in one minute, and we don’t break existing live flow while upgrading.

## ✅ To‑do

- [ ] Create `docs/COACH_UPGRADE_INDEX.md` as the single entry-point for this plan.
- [ ] Add a short “truth table” section that states clearly:
  - [ ] Live WS coach path uses `coach/` and the real simulator combat engine.
  - [ ] REST API server uses `src/models/` (legacy) unless/until migrated.
- [ ] Add a “Known fidelity gaps → coach behavior” paragraph:
  - [ ] simulator used for **ranking** options is safer than quoting absolute winrates
  - [ ] add UI phrasing rules (ex: “in sims” / “in our engine”)
- [ ] Add a “Run these to verify baseline health” section:
  - [ ] `python -m simulator.benchmark`
  - [ ] `python -m simulator.validate_output <some_results_dir>`
  - [ ] `pytest` (or your current test runner)

## 📦 Artifacts
- `docs/COACH_UPGRADE_INDEX.md`

## 🧪 Acceptance
- Existing live WS path still runs.
- Existing simulator benchmark still passes determinism.
- No code changes in this milestone should change model outputs.

---

# Milestone 1 — Contracts & schemas (make the interfaces explicit)

Goal: stop silent breakage. Codex needs explicit schemas to implement safely.

## ✅ To‑do

### 1.1 LiveState → CoachState conversion contract
- [ ] Write `docs/specs/LIVE_TO_COACH_STATE_CONTRACT.md` describing:
  - [ ] Required fields (must exist)
  - [ ] Optional fields (may be missing)
  - [ ] Defaulting rules (what happens when missing)
  - [ ] Invariants (board cap, item limits, position bounds)
  - [ ] Derived fields (traits computed vs trusted)
- [ ] Add a `schema_version` field to the coach-facing `GameState` (or the outgoing WS payload).
- [ ] Implement a runtime validator function:
  - [ ] `validate_coach_state(state) -> list[str]` (returns errors)
  - [ ] WS server logs errors and degrades gracefully (no crash).

### 1.2 SnapshotRow schema (collector output)
- [ ] Write `docs/specs/SNAPSHOT_ROW_SCHEMA.md`:
  - [ ] List every column the collector outputs (names + types)
  - [ ] Clarify timing (“pre-combat snapshot”)
  - [ ] Include at least 1 redacted example row
  - [ ] Include schema versioning rule (bump version on breaking changes)
- [ ] Add `row_schema_version` into collector output (if not already).

### 1.3 Coach explanation payload schema
- [ ] Write `docs/specs/COACH_EXPLANATION_SCHEMA.md`:
  - [ ] What modules return (`items`, `position`, `econ`, `shop`)
  - [ ] How recommendations are shaped for UI
  - [ ] Required numeric fields (winprob delta, expected HP delta, gold delta, interest delta, etc)
  - [ ] Confidence bucket rules
  - [ ] Phrasing rules (avoid absolute statements when low confidence)

### 1.4 Model artifact loading schema
- [ ] Write `docs/specs/MODEL_ARTIFACT_SCHEMA.md`:
  - [ ] how runtime coach loads evaluator models
  - [ ] versioning of feature engineering and vocabularies (champion ids, item ids, augment ids)
  - [ ] compatibility checks at load time

## 📦 Artifacts
- `docs/specs/LIVE_TO_COACH_STATE_CONTRACT.md`
- `docs/specs/SNAPSHOT_ROW_SCHEMA.md`
- `docs/specs/COACH_EXPLANATION_SCHEMA.md`
- `docs/specs/MODEL_ARTIFACT_SCHEMA.md`

## 🧪 Acceptance
- `validate_coach_state` is called in WS server and surfaces errors clearly.
- Snapshot schema doc matches actual collector output (spot check).
- Coach explanation payload shape is stable and documented.

---

# Milestone 2 — Unify the “ActionPlan” + “ScoreBreakdown” primitives across modules

Goal: every decision module speaks the same language, so scoring and explanations are consistent.

## ✅ To‑do

### 2.1 Define shared primitives
- [ ] Add shared dataclasses (or Pydantic models) somewhere central to the coach layer:

`ActionPlan` (minimum fields)
- `decision_type`: enum (`items|position|econ|shop`)
- `action_id`: stable string id (for logging + UI)
- `title`: short label
- `details`: structured payload (module-specific)
- `constraints`: optional (ex: requires_remover, requires_shop_visible)
- `tags`: list[str] for UI filtering (tempo, greed, stabilize, pivot, etc)

`ScoreBreakdown` (minimum fields)
- `total_score`: float
- `tempo`: { `win_prob`: float, `win_prob_delta`: float, `expected_hp_delta`: float, `n_sims`: int, `ci95`: optional }
- `evaluator`: { `board_score`: float, `matchup_score`: optional, `uncertainty`: optional }
- `econ`: { `gold_delta`: int, `interest_delta`: int, `level_delta`: int, `roll_delta`: int, `hp_risk`: float }
- `archetype`: { `top_archetypes`: list, `alignment_delta`: float }
- `penalties`: list of {reason, amount}

`Recommendation`
- `action`: ActionPlan
- `score`: ScoreBreakdown
- `explanation`: structured fields for UI (see schema doc)

### 2.2 Standardize module interfaces
For each module (`items`, `position`, `econ`, `shop`), implement:

- [ ] `generate_candidates(state) -> list[ActionPlan]`
- [ ] `execute(state, action: ActionPlan) -> new_state`
- [ ] `explain(state, action, score_breakdown) -> explanation_payload`

### 2.3 Add logging hooks (minimal)
- [ ] Add a `DecisionTrace` object:
  - state hash/id
  - baseline score (no-op action)
  - candidates list
  - scores list
  - chosen action id
  - sim seeds + counts
- [ ] Write traces as JSONL to `outputs/coach/traces/` (or similar)

## 📦 Artifacts
- Shared dataclasses + logger
- JSONL traces produced for live sessions

## 🧪 Acceptance
- All modules return the same recommendation shape.
- UI receives consistent payload keys across modules.
- A single debug print can show “top 3 actions + breakdown”.

---

# Milestone 3 — Combat scoring engine hardening (caching + seeds + adaptive budgets)

Goal: make sims trustworthy, fast, and comparable.

## ✅ To‑do

### 3.1 Deterministic seeding and “common random numbers”
- [ ] Implement seed control in combat scoring:
  - [ ] `simulate(board_a, board_b, seeds: list[int])`
- [ ] When comparing candidates A vs B, use the **same seed list** for both.
- [ ] Store the seed list in the trace and explanation payload (optional).

### 3.2 Caching
- [ ] Define a stable hash for “combat input”:
  - [ ] board units + stars + items + positions + augments/traits if combat uses them
- [ ] Cache per-matchup results:
  - key = (hash_a, hash_b, seed_block_id)
  - value = outcomes summary
- [ ] Add cache size limits (LRU or TTL) to avoid memory blowups.

### 3.3 Opponent selection policy (live + fallback)
- [ ] If the live state includes the next opponent board, score vs that.
- [ ] Else:
  - [ ] score vs a small set of “likely opponent archetype boards” sampled from an artifact
  - [ ] or score vs a set of recently seen opponent boards (if the coach tracks them)

### 3.4 Adaptive sim budgets (“coarse → refine”)
Implement a policy like:
- Pass 1: 64–128 sims for all candidates
- Pass 2: 256 sims for top K candidates
- Pass 3: 512–1024 sims for top 2 when close

Codex should implement this as a generic function:

`rank_candidates_with_budget(candidates, score_fn, budget_policy) -> ranked`

Budget policy should support:
- max total sims per decision
- max sims per candidate
- “tie threshold” for additional refinement

### 3.5 Robust aggregation
- [ ] Support at least these aggregations:
  - mean win_prob across opponents
  - worst_case win_prob across opponents (optional)
  - expected_hp_delta across opponents

### 3.6 CI-friendly unit tests
- [ ] Add tests that run a tiny deterministic matchup twice and assert identical results.
- [ ] Add tests that verify cache hits occur.

## 📦 Artifacts
- Combat scorer that returns winprob + expected HP delta + n_sims + CI/uncertainty estimate
- Budget policy implementation
- Cache implementation

## 🧪 Acceptance
- Same state + same seeds → identical winprob outputs.
- Candidate ranking is stable under repeated calls.
- Performance: scoring does not scale linearly with “number of candidates × max_sims” due to adaptive refinement.

---

# Milestone 4 — Items module: candidate generation + deterministic execution + sim-backed scoring

Goal: make item advice “surgical” and trustworthy.

## ✅ To‑do

### 4.1 Candidate generation (branch factor control)
- [ ] Enumerate all legal completed items from current components:
  - [ ] include “hold components” option
  - [ ] include “slam tempo” options (even suboptimal long-term)
- [ ] Enumerate plausible target units:
  - [ ] on-board units
  - [ ] primary carry candidate(s)
  - [ ] primary tank candidate(s)
  - [ ] secondary carry/support
  - Use archetype priors if available; otherwise use simple heuristics:
    - highest DPS proxy for carry
    - highest HP/armor proxy for tank
- [ ] Cap candidates:
  - [ ] hard cap like 50–80 candidates
  - [ ] dedupe by (item, target_unit_id)

### 4.2 Deterministic executor
- [ ] `execute_item_action(state, action)` should:
  - [ ] combine components if needed
  - [ ] place item on target unit
  - [ ] enforce max 3 items/unit
  - [ ] update item bench inventory
  - [ ] handle illegal action by returning error, not crashing

### 4.3 Scoring
- [ ] Score each candidate next-state:
  - [ ] combat score delta vs baseline (no-op)
  - [ ] evaluator board score delta (fast proxy)
  - [ ] archetype alignment delta
  - [ ] small penalty for “locks you out of better slam” if you model that (optional)
- [ ] Use adaptive sim budgets from Milestone 3.

### 4.4 Explanation output
- [ ] Provide:
  - [ ] item name + target unit
  - [ ] winprob delta (“in sims vs next opponent”)
  - [ ] expected HP delta
  - [ ] note if this is “tempo slam” vs “best-in-slot” for your likely archetype
  - [ ] confidence bucket

### 4.5 Tests
- [ ] Unit tests for:
  - [ ] legality checks (cannot exceed 3 items)
  - [ ] component consumption is correct
  - [ ] candidate count bounded
- [ ] Integration test:
  - [ ] from a known state, ensure top recommendation is stable under seeds

## 📦 Artifacts
- Robust item recommender with sim-backed deltas
- UI-ready explanations

## 🧪 Acceptance
- In a “close fight” scenario, item slam recommendations produce measurable tempo improvement in sims.
- No illegal item recommendations reach the UI.

---

# Milestone 5 — Position module: templates + perturbations + robust sim ranking

Goal: positioning advice that’s opponent-aware and doesn’t overfit to one seed.

## ✅ To‑do

### 5.1 Define layout templates
Implement a small template library, e.g.:
- corner carry
- center carry
- split carries
- clumped frontline
- spread frontline
- anti-assassin pattern
- scout-counter (if opponent info available)

Each template should be a deterministic mapping:
`template(placeable_units, board_shape) -> positions`

### 5.2 Local perturbations
- [ ] For each template, generate 5–15 perturbations:
  - [ ] swap two frontline units
  - [ ] shift carry 1 hex left/right
  - [ ] spread vs clump adjustments
- [ ] Ensure uniqueness and legality (no collisions, within bounds).

### 5.3 Scoring
- [ ] Score each layout vs:
  - [ ] known opponent board if available
  - [ ] else small opponent set
- [ ] Robust metric:
  - [ ] prioritize mean winprob
  - [ ] tie-break with worst-case winprob
- [ ] Adaptive sim budget:
  - coarse evaluate all layouts
  - refine top layouts

### 5.4 Explanation
- [ ] Provide:
  - [ ] “why this beats the opponent” tags (assassin threat, AOE, hook, etc) if detectable
  - [ ] winprob delta and expected HP delta
  - [ ] mention robustness (“best across likely opponents”)

### 5.5 Tests
- [ ] Unit tests:
  - [ ] valid positions
  - [ ] no duplicate occupancy
  - [ ] stable outputs per template
- [ ] Integration test with a fixed opponent board and seed list.

## 📦 Artifacts
- Positioning recommender producing ranked layouts + deltas

## 🧪 Acceptance
- For a known opponent board, the module produces consistent layout rankings under repeated runs.
- Explanations include concrete numeric deltas.

---

# Milestone 6 — Econ module: short-horizon lookahead with HP risk

Goal: replace econ “vibes” with quantified risk and expected payoff.

## ✅ To‑do

### 6.1 Define econ action plans
Support plans like:
- Save to maintain interest breakpoint
- Level now
- Roll down to X gold (50/30/20/10/0)
- Stabilize until you hit 1 upgrade or spend Y gold
- “Push level then roll” (two-step plan, optional)

Represent each as an `ActionPlan` with explicit parameters.

### 6.2 Deterministic econ executor
- [ ] Apply gold spend for XP
- [ ] Apply shop refresh cost and update shop state if live shop is modeled
- [ ] Ensure interest breakpoints computed correctly
- [ ] Update level/xp/gold deterministically

### 6.3 Lookahead simulation (Monte Carlo)
Implement a short-horizon evaluator:
- Horizon: 1–2 rounds
- Samples: N shop sequences
- For each sample:
  - [ ] simulate shop rolls (using odds by level + pool model if available)
  - [ ] apply a simple buy heuristic (or reuse shop module in “fast mode”)
  - [ ] compute combat score for the next fight (tempo)
  - [ ] compute HP risk (probability of losing and expected damage)

Return:
- expected winprob next fight
- expected HP delta next fight
- expected gold after action(s)
- probability of “stabilized” (hit at least one upgrade), if defined

### 6.4 Explanation
- [ ] Provide:
  - [ ] interest breakpoint effects (“keeps 50g”, “drops to 30g”)
  - [ ] quantified HP risk change (“expected damage -4.2”)
  - [ ] why the recommendation is tempo vs greed

### 6.5 Tests
- [ ] Determinism under fixed seeds for the shop sequence simulator.
- [ ] Candidate count bounded.
- [ ] No illegal negative gold / impossible XP states.

## 📦 Artifacts
- Econ advisor with quantifiable tradeoffs

## 🧪 Acceptance
- In low-HP scenarios, econ module prefers stabilize lines that reduce expected HP loss.
- In high-HP/high-gold scenarios, econ module preserves interest and levels efficiently.

---

# Milestone 7 — Shop module: concrete buy plans, not macro labels

Goal: the shop module proposes executable buy/sell/roll plans and the coach scores them like everything else.

## ✅ To‑do

### 7.1 Candidate generation (requires shop visibility policy)
Support two modes:

Mode A (shop visible):
- [ ] candidates use actual shop slots
- [ ] generate plans like:
  - buy upgrades (complete 2★/3★)
  - buy trait breakpoint enablers
  - buy high-value standalone unit (if it’s truly strong)
  - buy pairs for bench
  - lock if shop is strong
  - roll N times then buy best (bounded)

Mode B (shop not visible):
- [ ] generate “intent plans” that are evaluated by lookahead (like econ module)
- [ ] keep output conservative (don’t pretend you know the shop)

### 7.2 Deterministic shop executor
- [ ] implement:
  - buying units
  - selling units
  - bench capacity enforcement
  - board cap enforcement
  - gold deltas
  - lock state (if tracked)
  - roll count (if shop can be advanced)

### 7.3 Scoring
- [ ] Score resulting next-states with:
  - combat delta (if board changes)
  - evaluator score delta
  - econ penalties (gold/interest)
  - archetype alignment delta
- [ ] Use adaptive sim budgets.

### 7.4 Explanation
- [ ] Provide:
  - [ ] what you bought/sold
  - [ ] what upgrade or breakpoint it creates
  - [ ] cost vs interest impact
  - [ ] tempo delta in sims if applicable

### 7.5 Tests
- [ ] Ensure no plan exceeds bench size.
- [ ] Ensure board cap obeyed.
- [ ] Dedupe identical buy sets.

## 📦 Artifacts
- Shop recommender producing concrete plan(s)

## 🧪 Acceptance
- With shop visibility, the top recommendation is stable under repeated runs.
- Without shop visibility, output is explicitly labeled as “plan/intent” and uses lookahead, not hallucinated buys.

---

# Milestone 8 — Archetype library: build + load + use (priors, not dictators)

Goal: give the coach a “meta compass” so it stops suggesting incoherent pivots.

## ✅ To‑do

### 8.1 Build archetypes offline
Data sources (choose one or both):
- simulator finals (from `cloud_runner` end states)
- scraped high-elo finals (optional, for realism)

Representation for clustering:
- unit counts weighted by star and cost
- trait counts / tiers
- key item signatures (carry/tank items)
- augment signatures (coarse or top-N)

Clustering approach:
- start with k-means (easy) with “generous k”
- store cluster summaries

### 8.2 Artifact schema
Archetype artifact should include:
- `schema_version`
- archetype id + name
- core units (freq)
- common traits (freq)
- common carry units + items
- top4 rate (if available)
- example boards (optional)
- embedding centroid for similarity queries

### 8.3 Runtime API
Implement functions:
- `closest_archetypes(state, top_n=3) -> list[ArchetypeMatch]`
- `suggest_carry_candidates(state) -> list[UnitRef]`
- `suggest_items_for_archetype(archetype_id) -> list[item_id]`

### 8.4 Integrate into modules
- [ ] Items module uses archetype to prioritize carry/tank candidates.
- [ ] Shop module uses archetype to bias candidate buys.
- [ ] Explanation mentions “closest archetype(s)” when helpful.

### 8.5 Tests
- [ ] Artifact loads cleanly.
- [ ] Similarity queries are stable.
- [ ] Missing artifact degrades gracefully (coach still runs).

## 📦 Artifacts
- `outputs/coach/archetypes/*.json` (or parquet) + manifest

## 🧪 Acceptance
- Coach recommendations become more coherent (less random unit grabbing).
- UI can display “You’re closest to X line” if desired.

---

# Milestone 9 — Evaluator integration: fast scoring + uncertainty buckets

Goal: use the existing `models/` stack to speed up and stabilize decision scoring.

## ✅ To‑do

### 9.1 Choose initial runtime evaluator
Start with something lightweight and reliable:
- XGBoost fight model (predict win probability of current matchup)
- Optional: top4 / placement head if available

### 9.2 Build a “runtime evaluator wrapper”
Requirements:
- loads a model artifact + feature version
- exposes:
  - `predict_fight_prob(state, opponent_state) -> float`
  - `predict_board_strength(state) -> float` (optional proxy)
- has a `check_compatibility()` that verifies:
  - champion id mapping version
  - item id mapping version
  - augment id mapping version
  - feature set version

### 9.3 Uncertainty buckets
Implement at least one uncertainty method:
- If transformer used: MC Dropout (already scaffolded)
- If XGBoost used: calibration + “distance to training distribution” proxy (or a simple confidence heuristic)

Define buckets:
- `high_confidence`
- `medium_confidence`
- `coin_flip`
- `low_confidence`

Wire uncertainty into explanations:
- avoid absolute phrasing when low confidence

### 9.4 Use evaluator to prune candidates (speed win)
- [ ] Before heavy sims:
  - [ ] score all candidates with evaluator quickly
  - [ ] keep top K
  - [ ] run sims only on top K
- [ ] Ensure this pruning is optional/tunable (weights.py).

### 9.5 Tests
- [ ] Evaluator wrapper deterministic for same input.
- [ ] Compatibility checks fail loudly with helpful message.

## 📦 Artifacts
- Runtime evaluator loader + config
- Confidence bucket outputs in coach payloads

## 🧪 Acceptance
- Candidate evaluation latency decreases while recommendation quality remains stable.
- Explanations contain confidence buckets.

---

# Milestone 10 — Live WS integration polish (payload stability + graceful degradation)

Goal: coach never takes down the live loop and UI always gets something usable.

## ✅ To‑do

### 10.1 Payload shape hardening
- [ ] Validate outgoing WS payload against `COACH_EXPLANATION_SCHEMA`.
- [ ] If a module fails:
  - [ ] return an error object for that module only
  - [ ] keep other modules’ outputs

### 10.2 State conversion robustness
- [ ] Ensure LiveState → CoachState conversion:
  - [ ] handles missing shop info
  - [ ] handles missing opponent info
  - [ ] handles missing augments/traits gracefully (derive where possible)

### 10.3 UI/Frontend expectations
- [ ] Add a “compatibility version” field:
  - [ ] `coach_payload_version`
- [ ] Add `debug` fields behind a flag (so UI can optionally show numeric details).

## 📦 Artifacts
- Stable WS payload contract enforced by code

## 🧪 Acceptance
- Live WS server doesn’t crash on partial/missing data.
- UI renders recommendations consistently across updates.

---

# Milestone 11 — Offline evaluation harness (prove improvements, prevent regressions)

Goal: measure that the coach is actually getting better.

## ✅ To‑do

### 11.1 Build an evaluation dataset
Use simulator decision-time snapshots as “states”:
- sample N states from Parquet chunks
- for each state:
  - run coach for one decision type (or all)
  - record recommended action and predicted deltas

### 11.2 Define offline metrics per module
Items / Position:
- average winprob delta vs baseline (no-op)
- percent of cases with positive delta
- robustness across opponent sets

Econ / Shop:
- expected HP delta change
- interest preservation vs tempo improvement tradeoff

### 11.3 Regression testing
- [ ] Save a fixed evaluation set + seed list.
- [ ] Run evaluation in CI and compare against last-known-good thresholds.

### 11.4 Trace viewer (optional but high leverage)
- [ ] Write a small script that reads `DecisionTrace` JSONL and prints:
  - top candidates with breakdown
  - why the chosen one won
  - seed/budget info

## 📦 Artifacts
- `outputs/coach/eval_reports/*.json`
- fixed eval set + seeds

## 🧪 Acceptance
- Every code change can be evaluated quickly.
- You can answer “did this change make item advice better?” with numbers.

---

# Milestone 12 — (Optional) Migrate legacy API server model usage

Goal: reduce confusion and duplicated logic.

This is optional, but recommended once the new path is stable.

## ✅ To‑do (choose one direction)

Option A: Keep legacy track but document it as legacy
- [ ] Add a clear doc note that `src/models/` is legacy and used only by REST API.
- [ ] Add a plan for eventual deprecation.

Option B: Migrate REST API to use `models/` artifacts
- [ ] Build an adapter layer so REST API calls the same evaluator wrapper used by coach.
- [ ] Remove duplicate minimal combat scaffold if no longer needed.

## 📦 Artifacts
- Reduced “two brains” ambiguity

## 🧪 Acceptance
- No production path is ambiguous about which model is being served.

---

## Appendix A — Required “guardrails” in code (do these early)

- Always label sim-derived numbers as “in sims” in explanations.
- Prefer ranking (“Option A > B”) over claiming absolute correctness.
- If opponent board unknown, explicitly say the evaluation used a generic opponent set.
- Enforce hard caps:
  - max candidates per module
  - max total sims per decision
  - max refinement passes
- Every executor must be deterministic and legality-checked.

---

## Appendix B — Default tuning knobs (centralize these)

Create a single config surface (ex: `coach/weights.py` or `coach/config.py`) with:

- `MAX_CANDIDATES_ITEMS`
- `MAX_CANDIDATES_POSITION`
- `MAX_CANDIDATES_ECON`
- `MAX_CANDIDATES_SHOP`
- `SIM_BUDGET_PASS1`, `SIM_BUDGET_PASS2`, `SIM_BUDGET_PASS3`
- `TOPK_REFINE`
- Scoring weights:
  - `W_TEMPO`, `W_EVAL`, `W_ECON`, `W_ARCH`, `W_RISK`
- Confidence thresholds:
  - `HIGH_CONF`, `MED_CONF`, `COIN_FLIP`

Codex should ensure all modules use this config and do not hardcode budgets in random files.

---

## Appendix C — Minimal “Definition of Done” checklist (for each milestone PR)

- [ ] New code has unit tests.
- [ ] New artifacts have schema_version fields.
- [ ] New runtime outputs match explanation schema.
- [ ] Candidate counts are capped and logged.
- [ ] Determinism under seeds verified for combat scoring.
- [ ] Trace logging works and is readable.

