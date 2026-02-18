"""Cython-accelerated feature engineering helpers.

Build:
    cd models/fe_fast && python setup.py build_ext --inplace
"""

try:
    from .fe_fast import team_summary_fast, parse_units_column_fast  # type: ignore[import-not-found]
    CYTHON_AVAILABLE = True
except ImportError:
    team_summary_fast = None  # type: ignore[assignment]
    parse_units_column_fast = None  # type: ignore[assignment]
    CYTHON_AVAILABLE = False
