"""Build the Cython fe_fast extension.

Usage:
    cd models/fe_fast
    python setup.py build_ext --inplace

The compiled module provides accelerated versions of:
- team_summary_fast()
"""

import sys

from Cython.Build import cythonize
from setuptools import Extension, setup

if sys.platform == "win32":
    extra_compile_args = ["/O2"]
else:
    extra_compile_args = ["-O3"]

extensions = [
    Extension(
        "fe_fast",
        sources=["fe_fast.pyx"],
        extra_compile_args=extra_compile_args,
    )
]

setup(
    name="fe_fast",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "language_level": "3",
        },
    ),
)
