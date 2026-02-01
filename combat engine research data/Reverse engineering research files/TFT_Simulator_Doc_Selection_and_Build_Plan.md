# Deterministic TFT Combat Simulator — Doc Selection and Build Plan
*Report date: 2026-02-01*

## What to keep “active” for the simulator
You currently have 5 research docs. The best outcome comes from **choosing one canonical spec**, then demoting the rest into supporting roles so they stop competing.

### Canonical spec source
**Keep as the primary source (and convert into a single markdown spec):**
- `Researching TFT Combat Timing Constants.docx`

Why: it contains the strongest “systems model” framing (tick architecture, state machine, quantized timing) and is the closest to an implementable blueprint.

### Supporting sources (do not treat as authoritative specs)
**Use as an appendix and measurement SOP:**
- `Deterministic TFT Combat Simulator – Technical Research Report.docx`

Why: it’s an excellent protocol for measurement, capture, and cue identification. It belongs inside the spec as a “Measurement Protocol” section, or as an appendix.

**Use as background and validation philosophy:**
- `research-TFT Combat Timing Analysis and Error Propagation Framework.docx`

Why: it’s good for onboarding and explaining why error + ordering issues matter. Keep its best parts, but don’t let it dictate build scope or tool sprawl.

**Keep as a short intro/overview (optional):**
- `TFT_Combat_Timing_Research_Report.md`

Why: it’s readable and motivating. It’s useful as an executive summary, but it should link to the canonical spec instead of duplicating it.

**Keep as a tooling artifact only:**
- `TFT_TIMING_ANALYSIS_RESEARCH_PROMPT.md`

Why: prompts evolve. This should never be the place where requirements or success metrics “live”.

---

## What to produce next (1 markdown spec + 2 support docs)

### 1) Create the single source of truth
Create: `docs/simulator/DETERMINISTIC_SIM_SPEC.md`

It should contain:
1. Purpose and success metrics (measurable, testable)
2. Glossary (tick, event, resolution, windup, etc.)
3. System model
   - tick loop rules
   - event queue structure (tick, priority, tiebreaker)
   - RNG policy and determinism rules
4. Combat entity state machine (auto-attack cycle, movement stub, cast stub)
5. **Event ordering and tie-breakers** (explicit, test-backed)
6. Parameter sourcing strategy (extractable vs video-measurable vs inference-only)
7. Measurement protocol appendix (ported from the measurement report)
8. Validation plan and test suite design (micro-tests → scenario tests → distributions)
9. Decision log format (every new discovered rule is logged)

### 2) Create a “measurement only” appendix
Create: `docs/simulator/MEASUREMENT_PROTOCOL.md`

This is where high-FPS capture guidance and cue selection live. Keep it separate so the spec stays buildable even before you measure anything.

### 3) Create a “validation harness” doc
Create: `docs/simulator/VALIDATION_HARNESS.md`

Define:
- micro-test library (unit tests for ordering rules)
- scenario fixtures
- event log format
- determinism check procedure

---

## Why this consolidation matters
Your biggest accuracy risk is not “I measured a windup wrong by 8ms”.
Your biggest risk is “two things happened inside one tick, and we guessed the order wrong”.

So the docs must reflect that reality:
- Timing constants are important.
- Ordering rules and tie-breakers are existential.

This is why the spec must have a first-class “Event Ordering and Tie-breakers” section, and why micro-tests are mandatory.

---

## Concrete build milestones (what “done” looks like)
### Milestone 1: Deterministic skeleton
- tick loop + event queue + RNG injection
- stable unit IDs + tiebreaker policy
- JSONL event log
- determinism test (two runs, identical hash)

### Milestone 2: Auto-attacks + targeting
- acquisition + windup + fire + backswing
- deterministic targeting rule + tie-breakers
- 5+ micro-tests

### Milestone 3: Ordering rules
- simultaneous deaths
- target dies mid-tick behavior
- same-tick damage + on-hit ordering (stubs acceptable, but ordering must be explicit)
- scenario replay harness with golden logs

Only after Milestone 3 should you start expanding into:
- abilities
- items
- augments
- overtime
- video-derived timing refinements

---

## How your existing docs map into the new spec
- The “systems model” and state machine from `Researching TFT Combat Timing Constants.docx` becomes Sections 3–5 of the spec.
- The capture/measurement protocol from `Deterministic TFT Combat Simulator – Technical Research Report.docx` becomes the appendix (or MEASUREMENT_PROTOCOL.md).
- The error modeling and validation ideas from the error propagation framework become Section 8 + the validation doc.
- The existing markdown research report becomes the executive summary at the top of the spec (trimmed down).
- The prompt stays as a tool for future research requests, not as requirements.

---

## Immediate next action in the repo
Add the simulator package scaffold (even empty modules) under `src/sim/` and create the determinism test harness first.

That single move forces the project to become implementable and test-driven instead of endlessly research-driven.
