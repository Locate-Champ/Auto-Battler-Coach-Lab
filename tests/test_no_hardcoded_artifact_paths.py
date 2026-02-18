from __future__ import annotations

import re
from pathlib import Path


FORBIDDEN_SUBSTRINGS = (
    "outputs/",
    "models/checkpoints",
)

FORBIDDEN_LITERAL_PATTERN = re.compile(r"""['"](outputs|checkpoints)['"]""")


def test_scoring_modules_do_not_hardcode_artifact_paths() -> None:
    scoring_dir = Path(__file__).resolve().parents[1] / "coach" / "scoring"
    files = sorted(scoring_dir.glob("*.py"))
    assert files, "Expected coach/scoring python modules to exist"

    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SUBSTRINGS:
            assert token not in text, f"Found forbidden path token '{token}' in {path}"
        assert not FORBIDDEN_LITERAL_PATTERN.search(text), (
            f"Found forbidden path literal ('outputs'/'checkpoints') in {path}"
        )
