"""
This is here to tell pytest that this is the source folder.
"""

import sys
from pathlib import Path

_simulator_root = Path(__file__).resolve().parent
_simulator_path = str(_simulator_root)
if _simulator_path not in sys.path:
    sys.path.insert(0, _simulator_path)
