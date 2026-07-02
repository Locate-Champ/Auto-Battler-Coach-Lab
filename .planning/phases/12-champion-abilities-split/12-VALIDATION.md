---
phase: 12
slug: champion-abilities-split
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-02
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7 |
| **Config file** | pyproject.toml (project root) |
| **Quick run command** | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` |
| **Full suite command** | `python -m pytest && python -m simulator.benchmark` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -c "from simulator.core.champion_abilities import ChampionAbilities"` + `ruff check .` + `ruff format --check .`
- **After every plan wave:** Run `python -m simulator.benchmark` (determinism gate)
- **Before `/gsd:verify-work`:** Full suite must be green (`python -m pytest` + `python -m simulator.benchmark`)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | SPLT-04 | smoke | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` | N/A (CLI) | ⬜ pending |
| 12-01-02 | 01 | 1 | SPLT-06 | integration | `python -m simulator.benchmark` | ✅ | ⬜ pending |
| 12-01-03 | 01 | 1 | SPLT-05 | smoke | `python -c "from simulator.core.champion_abilities import ChampionAbilities"` | N/A (CLI) | ⬜ pending |
| 12-01-04 | 01 | 1 | BNCH-01 | integration | `python -m pytest tests/test_benchmark_parity_helpers.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed; benchmark.py and existing tests are sufficient.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
