"""Cython-accelerated feature engineering helpers.

Build:
    cd models/fe_fast && python setup.py build_ext --inplace
"""

import logging

_log = logging.getLogger(__name__)

try:
    from .fe_fast import (  # type: ignore[import-not-found]
        parse_units_column_fast,
        team_summary_fast,
    )

    CYTHON_AVAILABLE = True
except (ImportError, OSError):
    team_summary_fast = None  # type: ignore[assignment]
    parse_units_column_fast = None  # type: ignore[assignment]
    CYTHON_AVAILABLE = False
    _log.warning(
        "Cython fe_fast module not available; feature extraction will use pure-Python path "
        "(~2x slower). Build with: cd models/fe_fast && python setup.py build_ext --inplace"
    )
