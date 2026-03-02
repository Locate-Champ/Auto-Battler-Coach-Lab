---
phase: 13
slug: obsv-verification-and-logging-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-02
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `ruff check . && ruff format --check .`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | OBSV-01 | inspection | `grep -n "_log.warning" models/fe_fast/__init__.py` | N/A | pending |
| 13-01-02 | 01 | 1 | OBSV-02 | inspection | `grep -n "_log.warning" models/data_loader.py` | N/A | pending |
| 13-01-03 | 01 | 1 | OBSV-03 | unit | `ruff check . && python -m pytest` | existing | pending |
| 13-01-04 | 01 | 1 | OBSV-03 | grep | `grep -rn "^print\b" simulator/_cloud_runner_core.py simulator/_cloud_runner_utils.py models/_feature_engineering_transform.py models/_feature_engineering_batch.py` | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OBSV-01 fallback log | OBSV-01 | Requires Cython to be absent | Import `models.fe_fast` without Cython installed, check WARNING log emitted |
| OBSV-02 fallback log | OBSV-02 | Requires pyarrow to be absent | Import DataLoader without pyarrow, check WARNING log emitted |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
