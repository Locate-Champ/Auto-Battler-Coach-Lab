from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_PREFIXES = (
    "Simulator",
    "Concurrency",
    "Evaluator",
    "simulator.Simulator",
    "simulator.Concurrency",
    "simulator.Evaluator",
)


def iter_py_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return [p for p in base.rglob("*.py") if p.is_file()]


def parse_imports(py_path: Path) -> set[str]:
    src = py_path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(py_path))
    mods: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Ignore relative imports like "from . import x"
                if node.level and node.level > 0:
                    continue
                mods.add(node.module)
    return mods


def has_prefix(mod: str, prefix: str) -> bool:
    return mod == prefix or mod.startswith(prefix + ".")


def assert_no_legacy_imports(files: list[Path], label: str) -> None:
    violations: list[str] = []
    for f in files:
        mods = parse_imports(f)
        for m in mods:
            for pref in LEGACY_PREFIXES:
                if has_prefix(m, pref):
                    violations.append(f"{f.as_posix()}: imports legacy '{m}'")
    assert not violations, f"{label} contains legacy imports:\n" + "\n".join(violations)


def test_api_server_does_not_import_training_models() -> None:
    target = REPO_ROOT / "app" / "api" / "server.py"
    assert target.exists(), "Expected app/api/server.py to exist"
    mods = parse_imports(target)

    bad = [m for m in mods if has_prefix(m, "models")]
    assert not bad, "app/api/server.py must not import training track 'models':\n" + "\n".join(bad)

    provider_specific = [m for m in mods if has_prefix(m, "src.metatft_parser")]
    assert not provider_specific, (
        "app/api/server.py must not import provider-specific parser modules:\n"
        + "\n".join(provider_specific)
    )


def test_training_track_does_not_import_runtime_src_models() -> None:
    base = REPO_ROOT / "models"
    files = iter_py_files(base)
    violations: list[str] = []
    for f in files:
        mods = parse_imports(f)
        for m in mods:
            if has_prefix(m, "src.models"):
                violations.append(f"{f.as_posix()}: imports runtime track '{m}'")
    assert not violations, "models/** must not import src.models:\n" + "\n".join(violations)


def test_runtime_paths_do_not_import_legacy_simulator_packages() -> None:
    app_files = iter_py_files(REPO_ROOT / "app")
    coach_files = iter_py_files(REPO_ROOT / "coach")
    assert_no_legacy_imports(app_files + coach_files, "app/** and coach/**")


def test_active_simulator_paths_do_not_import_legacy_packages() -> None:
    active_files: list[Path] = []
    active_files += iter_py_files(REPO_ROOT / "simulator" / "core")
    active_files += iter_py_files(REPO_ROOT / "simulator" / "game")

    for rel in [
        "simulator/cloud_runner.py",
        "simulator/validate_output.py",
        "simulator/benchmark.py",
    ]:
        p = REPO_ROOT / rel
        if p.exists():
            active_files.append(p)

    assert_no_legacy_imports(active_files, "active simulator paths")
