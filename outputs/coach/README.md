# outputs/coach runtime artifact contract

This directory is the only tracked subset of `outputs/`.

Runtime scoring reads artifacts from here.

Everything else under `outputs/` is generated and should not be committed.

Regenerate artifacts:

- `python -m coach.offline.build_knowledge_base`
- `python -m coach.offline.train_evaluator --input-dir <results_dir>`
- `python -m coach.offline.eval_coach --input-dir <results_dir> --output outputs/coach/eval_reports/<report>.json` (TBD exact baseline args as needed)
