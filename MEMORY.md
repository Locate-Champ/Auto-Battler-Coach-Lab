# MEMORY.md — Auto-Battler Coach Lab

Stable memory: invariants + runbooks.

## Invariants
- Simulation is CPU-bound. Prefer CPU-heavy instances and the Rust engine when available.
- Training is GPU-bound. Don’t expect XGBoost ext-mem to use GPU well.
- Always smoke-test (100–1000 games) before “Gate sized” runs.
- Parquet is default. Verify pyarrow in the target python env.

## RUNBOOKS

### RUNBOOK: TFT_GATE_B_50K_SIM
Goal: produce a 50k validated dataset fast.
Steps:
1) Smoke:
   - python -m simulator.cloud_runner --games 200 --engine rust_full --workers 1 --output results/smoke
   - python -m simulator.validate_output results/smoke
2) Gate:
   - python -m simulator.cloud_runner --games 50000 --engine rust_full --workers 1 --output results/<RUN_ID> [plus your standard parquet flags]
3) Validate:
   - python -m simulator.validate_output results/<RUN_ID>
Done means: run completes with low errors and validation passes.

### RUNBOOK: TFT_XGB_TRAIN_FAST
Goal: avoid the 56-min Python row-vectorization path.
Rule: if the training script supports Arrow/Parquet fast path, use it.
Preflight:
- python -c "import pyarrow; print(pyarrow.__version__)"
Then run training with the Arrow/Parquet fast path enabled (your `--arrow` flag or equivalent).
Done means: artifacts saved where the repo expects them + training log shows expected dataset size.