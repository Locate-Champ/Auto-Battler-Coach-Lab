"""Cython-accelerated feature engineering helpers.

Build:
    cd models/fe_fast && python setup.py build_ext --inplace
"""

try:
    from .fe_fast import (  # type: ignore[import-not-found]
        parse_units_column_fast,
        team_summary_fast,
    )

    CYTHON_AVAILABLE = True
except ImportError:
    team_summary_fast = None  # type: ignore[assignment]
    parse_units_column_fast = None  # type: ignore[assignment]
    CYTHON_AVAILABLE = False
