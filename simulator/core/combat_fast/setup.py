"""Build the Cython combat_fast extension.

Usage:
    cd simulator/core/combat_fast
    python setup.py build_ext --inplace

The compiled module provides accelerated versions of:
- hex_distance_fast()
- calculate_damage_fast()
- apply_damage_with_shield()
- mana_on_damage()
- find_nearest_enemy_idx()
"""

from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "combat_fast",
        sources=["combat_fast.pyx"],
        extra_compile_args=["-O3", "-march=native"],
    )
]

setup(
    name="combat_fast",
    ext_modules=cythonize(extensions, compiler_directives={
        "boundscheck": False,
        "wraparound": False,
        "cdivision": True,
        "language_level": "3",
    }),
)
