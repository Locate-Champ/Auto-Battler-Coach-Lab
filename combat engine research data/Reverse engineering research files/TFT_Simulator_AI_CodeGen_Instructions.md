# TFT Coach — Deterministic Combat Simulator
## Instructions for AI Code Generators (Claude Code, ChatGPT, Copilot, etc.)
*Last updated: 2026-02-01*

These instructions are written for code-generation assistants working inside this repo. The goal is to implement a **deterministic**, **tick-based** TFT combat simulator that is good enough to generate synthetic training data and run controlled validation tests.

---

## 1) Non-negotiables (do not violate)

### Determinism
- Given the same **initial board state** and the same **RNG seed/stream**, the simulator must produce the same results every run.
- No use of global `random`. Use an injected RNG object (`random.Random(seed)` or a custom RNG) and thread it everywhere.

### Tick-based time
- The simulator runs on a fixed integer tick loop (`tick = 0..N`).
- All durations resolve on tick boundaries. Avoid floating-point scheduling as the source of truth.
- If you need sub-tick ordering, model it as **(tick, priority, tiebreaker)** in an event queue, not real-time floats.

### Event ordering must be explicit
The main source of “mystery divergence” is event ordering when multiple things happen in the same tick. Every event must have:
- `tick`
- `priority` (small int where lower = earlier, or vice versa, but pick one)
- `tiebreaker` (stable ordering key, e.g. unit_id, spawn_index, board_scan_index)

### Safe data sources only
- OK: static game data in `data/game_data/`, existing Overwolf/MetaTFT logs, and video-derived measurements (if we add them later).
- Not OK: memory reading, client modification, packet sniffing, anything that violates game integrity.

### Testing is part of the deliverable
Every meaningful logic addition must ship with:
- at least 1 unit test (micro-test) that isolates the rule
- a simple replay harness where a scenario can be re-run deterministically and compared to a golden event log

---

## 2) What to build first (strict order)

### Phase A — Simulator skeleton (no “real TFT” yet)
Deliver:
- A deterministic tick loop
- A minimal event queue with `(tick, priority, tiebreaker)`
- A stable ID scheme for units and spawned objects
- A canonical event log format (JSONL recommended)

### Phase B — Core combat primitives
Implement:
- Target selection (simple, deterministic rule)
- Auto-attack cycle: acquisition → windup → fire → backswing
- Damage application and death resolution

### Phase C — Tie-breakers and ordering rules
Implement explicit rules and tests for:
- simultaneous deaths
- “target dies mid-tick” retarget behavior
- multiple valid targets at equal distance
- multiple events landing on the same tick (damage + on-hit + CC, etc.)

Only after Phase C should you start chasing timing constants or animation-cue precision.

---

## 3) Repo integration guidelines

### Suggested module layout (Python)
Create a new package:

```
src/sim/
  __init__.py
  core/
    time.py            # tick constants, conversions, helpers
    rng.py             # RNG wrapper + deterministic helpers
    event_queue.py     # scheduling, priorities, tie-breakers
    log.py             # event log writer
  model/
    types.py           # dataclasses / pydantic for state
    board.py           # hex grid + distance
    unit.py            # unit state machine
  systems/
    targeting.py
    attacks.py
    damage.py
    status_effects.py  # stub at first
  scenarios/
    fixtures.py        # canonical test scenarios
  validate/
    replay.py          # rerun + compare golden logs
tests/
  test_sim_event_ordering.py
  test_sim_targeting_tiebreakers.py
  test_sim_autoattack_cycle.py
```

Follow existing repo style (small modules, readable names, minimal magic).

### Logging format
Use JSON Lines (one event per line), e.g.
- `tick`
- `event_type` (e.g. `attack_start`, `damage`, `death`, `retarget`)
- `source_unit_id`, `target_unit_id` (when applicable)
- `amount`, `tags` (when applicable)
- `ordering_key` (optional but useful for debugging)

---

## 4) Event priorities (initial proposal)
Use a single integer priority scheme. Start simple and evolve when evidence demands it.

Example (lower runs earlier):
1. `death_resolution`
2. `on_death_triggers` (stub)
3. `damage_application` (projectile impacts, melee hits)
4. `on_hit_triggers` (stub)
5. `cc_application` (stub)
6. `retarget_checks`
7. `attack_fire` scheduling
8. `attack_windup_start`
9. `movement_step` (stub)

Tie-breaker proposal:
- `tiebreaker = (unit_spawn_index, unit_id)` or `(board_scan_index, unit_id)`
- Must be stable and documented.

Important: The assistant must not “guess” ordering. If uncertain, implement the rule as a clearly labeled assumption and add a micro-test that will fail once we learn the true rule.

---

## 5) Micro-tests (required)
Add a small “scenario builder” so tests are easy to write.

Minimum test scenarios:
- **Simultaneous lethal damage**: two units kill each other in the same tick, verify deterministic winner/death order.
- **Equal-distance targeting**: two identical targets, verify stable tie-break selection.
- **Target dies mid-windup**: verify whether attack cancels or retargets (initial assumption must be explicit).
- **Two events same tick**: damage and a heal (or shield) on the same tick, verify ordering.

Each test should assert:
- final survivors
- at least one key event sequence snippet from the event log

---

## 6) Prompt template for code generators
Use this exact format when asking an AI to implement something:

**Context**
- Repo: TFT Coach
- Task: [single narrow task]
- Constraints: determinism, tick-based, explicit event ordering, include tests, no global random

**Deliverable**
- Files to create/modify
- What tests to add
- How to run tests

**Definition of done**
- Tests pass
- Determinism verified by running the same scenario twice and matching event log hash

**Notes**
- Any assumptions must be documented in-code and in the scenario test name.

---

## 7) What NOT to do
- Don’t implement abilities/augments/items early. Get ordering + targeting correct first.
- Don’t overfit to one fight replay. Use a battery of small, isolating tests.
- Don’t use floating time as the primary scheduler.
- Don’t silently change ordering. If ordering changes, update tests and document why.

---

## 8) “Two-run determinism check” (must exist)
Add a helper like:

- Run scenario with seed X → write event log → hash it
- Run again with seed X → write event log → hash it
- Hashes must match

Put it in `tests/test_sim_determinism.py`.

