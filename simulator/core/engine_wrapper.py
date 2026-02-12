"""Auto-detecting combat engine wrapper.

Tries to use the Rust combat engine for maximum performance,
falls back to the Python engine transparently.

Usage:
    from simulator.core.engine_wrapper import get_engine

    engine = get_engine()  # Returns Rust or Python engine
    result = engine.run_combat(team0, team1, seed=42)
"""

from pathlib import Path
from typing import List, Dict, Optional

_COMBAT_DATA_PATH = str(Path(__file__).parent.parent / "data" / "combat_data.json")


def _try_rust_engine():
    """Attempt to import and instantiate the Rust combat engine."""
    try:
        from tft_combat_engine import RustCombatEngine
        engine = RustCombatEngine(_COMBAT_DATA_PATH)
        return engine
    except ImportError:
        return None
    except Exception:
        return None


def _get_python_engine(**kwargs):
    """Import and instantiate the Python combat engine."""
    from simulator.core.combat_engine import CombatEngine
    return CombatEngine(**kwargs)


class HybridCombatEngine:
    """Wrapper that uses Rust engine when available, Python otherwise.

    For batch simulations, the Rust engine provides 10-50x throughput
    by avoiding Python interpreter overhead in the tight tick loop.
    """

    def __init__(self, prefer_rust: bool = True, logging_enabled: bool = False):
        self._rust_engine = _try_rust_engine() if prefer_rust else None
        self._python_engine = None
        self._logging_enabled = logging_enabled
        self.using_rust = self._rust_engine is not None

    @property
    def python_engine(self):
        """Lazy-init Python engine (only created when needed)."""
        if self._python_engine is None:
            self._python_engine = _get_python_engine(
                logging_enabled=self._logging_enabled
            )
        return self._python_engine

    def run_combat(self, team0, team1, *,
                   team0_augments: Optional[List[str]] = None,
                   team1_augments: Optional[List[str]] = None,
                   seed: Optional[int] = None,
                   verbose: bool = False) -> Dict:
        """Run a single combat simulation.

        Accepts either Unit objects (Python engine) or dict specs (Rust engine).
        If given Unit objects and Rust is available, auto-converts to dicts.
        """
        if self.using_rust and not verbose:
            # Convert Unit objects to dict specs if needed
            t0_specs = _to_specs(team0)
            t1_specs = _to_specs(team1)
            return self._rust_engine.run_combat(
                t0_specs, t1_specs,
                team0_augments=team0_augments,
                team1_augments=team1_augments,
                seed=seed,
            )
        else:
            # Fall back to Python (supports verbose logging)
            return self.python_engine.run_combat(
                team0, team1,
                verbose=verbose,
                team0_augments=team0_augments,
                team1_augments=team1_augments,
                seed=seed,
            )

    def create_unit(self, api_name, star_level, position, team, items=None):
        """Create a unit via the Python engine."""
        return self.python_engine.create_unit(
            api_name, star_level, position, team, items
        )

    def simulate_1v1(self, champ1: str, champ2: str, **kwargs) -> Dict:
        """Run multiple 1v1 simulations. Uses Rust for the combat loop."""
        if self.using_rust:
            return self._simulate_1v1_rust(champ1, champ2, **kwargs)
        return self.python_engine.simulate_1v1(champ1, champ2, **kwargs)

    def _simulate_1v1_rust(self, champ1: str, champ2: str,
                           star1: int = 1, star2: int = 1,
                           items1=None, items2=None,
                           augments1=None, augments2=None,
                           num_simulations: int = 100,
                           seed: int = None) -> Dict:
        """Run 1v1 sims using the Rust engine."""
        wins = {champ1: 0, champ2: 0}
        total_damage = {champ1: 0.0, champ2: 0.0}
        abilities_cast = {champ1: 0, champ2: 0}
        combat_times = []

        t0_spec = [{
            'api_name': champ1, 'star_level': star1,
            'position': [0, 3], 'team': 0,
            'items': items1 or [], 'traits': [],
        }]
        t1_spec = [{
            'api_name': champ2, 'star_level': star2,
            'position': [3, 3], 'team': 1,
            'items': items2 or [], 'traits': [],
        }]

        for i in range(num_simulations):
            sim_seed = (seed + i) if seed is not None else None
            result = self._rust_engine.run_combat(
                t0_spec, t1_spec,
                team0_augments=augments1,
                team1_augments=augments2,
                seed=sim_seed,
            )
            if result['winner'] == 0:
                wins[champ1] += 1
            else:
                wins[champ2] += 1
            total_damage[champ1] += result['team0_total_damage']
            total_damage[champ2] += result['team1_total_damage']
            abilities_cast[champ1] += result['team0_abilities_cast']
            abilities_cast[champ2] += result['team1_abilities_cast']
            combat_times.append(result['combat_time'])

        n = num_simulations
        return {
            'simulations': n,
            'win_rate': {
                champ1: round(wins[champ1] / n * 100, 1),
                champ2: round(wins[champ2] / n * 100, 1),
            },
            'avg_damage': {
                champ1: round(total_damage[champ1] / n, 1),
                champ2: round(total_damage[champ2] / n, 1),
            },
            'avg_abilities_cast': {
                champ1: round(abilities_cast[champ1] / n, 2),
                champ2: round(abilities_cast[champ2] / n, 2),
            },
            'avg_combat_time': round(sum(combat_times) / len(combat_times), 2),
        }


def _to_specs(units) -> list:
    """Convert Unit objects or dicts to Rust-compatible spec dicts."""
    specs = []
    for u in units:
        if isinstance(u, dict):
            specs.append(u)
        else:
            specs.append({
                'api_name': u.api_name,
                'star_level': u.star_level,
                'position': list(u.position),
                'team': u.team,
                'items': [i.name for i in u.items] if u.items else [],
                'traits': list(u.traits) if u.traits else [],
            })
    return specs


def get_engine(prefer_rust: bool = True, logging_enabled: bool = False) -> HybridCombatEngine:
    """Get the best available combat engine.

    Returns a HybridCombatEngine that transparently uses Rust when available.
    """
    engine = HybridCombatEngine(prefer_rust=prefer_rust, logging_enabled=logging_enabled)
    backend = "Rust" if engine.using_rust else "Python"
    return engine
