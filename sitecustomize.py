"""Ensure legacy simulator namespace imports resolve in all Python processes.

Ray workers import modules like `Models.*` and `Simulator.*` as top-level
packages. Add `<repo>/simulator` to `sys.path` early so those imports work in
workers and local tests consistently.
"""

from pathlib import Path
import sys

_repo_root = Path(__file__).resolve().parent
_simulator_root = _repo_root / "simulator"

if _simulator_root.is_dir():
    _simulator_path = str(_simulator_root)
    if _simulator_path not in sys.path:
        sys.path.insert(0, _simulator_path)
