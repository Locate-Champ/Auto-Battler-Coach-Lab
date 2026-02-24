"""Compatibility shim for modules that import `config` at top level.

This project stores simulator config at `simulator/config.py`, but many legacy
modules import `config` directly. Expose the simulator module under this name
so local runs and Ray workers resolve the same module object.
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

_simulator_root = _Path(__file__).resolve().parent / "simulator"
_simulator_path = str(_simulator_root)

if _simulator_root.is_dir() and _simulator_path not in _sys.path:
    _sys.path.insert(0, _simulator_path)

_pythonpath = _os.environ.get("PYTHONPATH", "")
if _simulator_root.is_dir() and _simulator_path not in _pythonpath.split(_os.pathsep):
    _os.environ["PYTHONPATH"] = (
        _simulator_path if not _pythonpath else _simulator_path + _os.pathsep + _pythonpath
    )

from simulator import config as _simulator_config

_sys.modules[__name__] = _simulator_config
