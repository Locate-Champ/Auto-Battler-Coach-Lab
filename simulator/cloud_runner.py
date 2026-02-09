"""Batch runner for mass TFT game simulations.

Runs N games in parallel across multiple CPU cores, collecting ML training
data and balance analytics. Features:
- Streaming output: writes training data in chunks to avoid OOM
- Checkpoint/resume: saves progress periodically, can resume interrupted batches
- Per-game error handling: one crash doesn't kill the batch
- Agent mixing: configurable distribution of agent types per game

Usage:
    python -m simulator.cloud_runner --games 1000 --workers 8 --output results/run_001
    python -m simulator.cloud_runner --games 10 --workers 1  # Quick test
    python -m simulator.cloud_runner --resume results/run_001  # Resume interrupted batch
    python -m simulator.cloud_runner --games 1000 --agent-mix random:50,econ:30,slam:20
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import random
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from simulator.game.game import TFTGame
from simulator.game.collector import GameCollector
from simulator.game.actions import MixedLobbyAgent, fast_random_agent

# 95% Wilson interval z-score
WILSON_Z_95 = 1.959963984540054

# Agent profile presets for cloud-scale runs.
# random -> legacy fast_random behavior (no lobby mixing).
AGENT_PROFILES = {
    'random': None,
    'mixed': {'random': 50, 'econ': 30, 'slam': 20},
    'ladder': {'random': 20, 'econ': 45, 'slam': 35},
}


class BatchAbort(Exception):
    """Raised when a run should stop early while preserving output state."""


def _pyarrow_available() -> bool:
    try:  # pragma: no cover - optional dependency
        import pyarrow  # noqa: F401
        return True
    except Exception:
        return False


def _wilson_interval(successes: int, trials: int,
                     z: float = WILSON_Z_95) -> Tuple[float, float]:
    """Wilson score interval for Bernoulli metrics."""
    if trials <= 0:
        return 0.0, 0.0

    p = successes / trials
    z2 = z * z
    denom = 1 + (z2 / trials)
    center = (p + (z2 / (2 * trials))) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / trials) + (z2 / (4 * trials * trials)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return low, high


def _validate_reference_data_preflight() -> None:
    """Fail-fast if simulator reference data is out of sync."""
    validator = Path(__file__).parent / 'data' / 'validate_reference_data.py'
    if not validator.exists():
        print(f"Warning: reference validator not found at {validator} (skipping)")
        return

    result = subprocess.run(
        [sys.executable, str(validator)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError("Simulator reference validation failed before batch run.")

# ── Per-Game Runner ──────────────────────────────────────────────────────

def run_game(args: Tuple) -> Dict:
    """Run a single game with error handling.

    Args:
        args: (game_id, seed, agent_mix_or_none) tuple.

    Returns:
        Dict with status='ok' and game data, or status='error' with traceback.
    """
    game_id, seed, agent_mix = args
    try:
        # Seed before agent assignment for determinism
        random.seed(seed)

        # Build agent
        if agent_mix:
            agent = MixedLobbyAgent(agent_mix)
            agent.assign_players()
            agent_fn = agent
        else:
            agent_fn = None  # TFTGame defaults to fast_random_agent

        collector = GameCollector(game_id)
        game = TFTGame(
            num_players=8,
            seed=seed,
            verbose=False,
            logging_enabled=False,
            collector=collector,
            agent_fn=agent_fn,
        )
        start = time.perf_counter()
        game.play()
        elapsed = time.perf_counter() - start

        return {
            'status': 'ok',
            'game_id': game_id,
            'seed': seed,
            'elapsed': round(elapsed, 3),
            'rounds': game.round_num,
            'placements': collector.placements,
            'training_rows': collector.get_training_rows(),
            'analytics': collector.get_analytics(),
        }
    except Exception:
        return {
            'status': 'error',
            'game_id': game_id,
            'seed': seed,
            'error': traceback.format_exc(),
        }


# ── Streaming Writer ─────────────────────────────────────────────────────

class StreamingWriter:
    """Writes simulation results incrementally to avoid holding all data in memory.

    Training data is flushed to chunk files every `chunk_size` games.
    Analytics counters are accumulated in memory (small footprint).
    Checkpoints are written periodically for resume capability.
    """

    def __init__(
        self,
        output_dir: str,
        chunk_size: int = 100,
        resume_state: Optional[Dict] = None,
        require_parquet: bool = False,
    ):
        self.output_dir = output_dir
        self.chunk_size = chunk_size
        self.require_parquet = require_parquet
        os.makedirs(output_dir, exist_ok=True)

        # Training row buffer (flushed every chunk_size games)
        self._row_buffer: List[Dict] = []
        self._games_in_buffer = 0

        # Running analytics (accumulated across all games)
        self._champ_placements: Counter = Counter()
        self._champ_placements_sq: Counter = Counter()
        self._champ_counts: Counter = Counter()
        self._champ_top4_counts: Counter = Counter()
        self._champ_win_counts: Counter = Counter()
        self._aug_placements: Counter = Counter()
        self._aug_placements_sq: Counter = Counter()
        self._aug_counts: Counter = Counter()
        self._aug_top4_counts: Counter = Counter()
        self._aug_win_counts: Counter = Counter()

        # Tracking
        self._completed_seeds: List[int] = []
        self._errors: List[Dict] = []
        self._sum_game_time = 0.0
        self._total_rounds = 0
        self._total_rows = 0
        self._chunk_idx = 0

        # Restore state if resuming
        if resume_state:
            self._completed_seeds = list(resume_state.get('completed_seeds', []))
            self._chunk_idx = resume_state.get('chunks_written', 0)
            self._total_rows = resume_state.get('total_rows', 0)
            self._sum_game_time = resume_state.get('sum_game_time', 0.0)
            self._total_rounds = resume_state.get('total_rounds', 0)
            self._champ_placements = Counter(resume_state.get('champ_placements', {}))
            self._champ_placements_sq = Counter(resume_state.get('champ_placements_sq', {}))
            self._champ_counts = Counter(resume_state.get('champ_counts', {}))
            self._champ_top4_counts = Counter(resume_state.get('champ_top4_counts', {}))
            self._champ_win_counts = Counter(resume_state.get('champ_win_counts', {}))
            self._aug_placements = Counter(resume_state.get('aug_placements', {}))
            self._aug_placements_sq = Counter(resume_state.get('aug_placements_sq', {}))
            self._aug_counts = Counter(resume_state.get('aug_counts', {}))
            self._aug_top4_counts = Counter(resume_state.get('aug_top4_counts', {}))
            self._aug_win_counts = Counter(resume_state.get('aug_win_counts', {}))

    @property
    def num_completed(self) -> int:
        return len(self._completed_seeds)

    @property
    def num_errors(self) -> int:
        return len(self._errors)

    def add_result(self, result: Dict):
        """Process a completed game result."""
        if result['status'] == 'error':
            self._errors.append({
                'game_id': result['game_id'],
                'seed': result['seed'],
                'error': result['error'],
            })
            return

        self._completed_seeds.append(result['seed'])
        self._sum_game_time += result['elapsed']
        self._total_rounds += result['rounds']

        # Buffer training rows
        self._row_buffer.extend(result['training_rows'])

        # Accumulate analytics
        analytics = result['analytics']
        for name, placement in analytics['champion_placements']:
            self._champ_placements[name] += placement
            self._champ_placements_sq[name] += placement * placement
            self._champ_counts[name] += 1
            if placement <= 4:
                self._champ_top4_counts[name] += 1
            if placement == 1:
                self._champ_win_counts[name] += 1
        for name, placement in analytics['augment_placements']:
            self._aug_placements[name] += placement
            self._aug_placements_sq[name] += placement * placement
            self._aug_counts[name] += 1
            if placement <= 4:
                self._aug_top4_counts[name] += 1
            if placement == 1:
                self._aug_win_counts[name] += 1

        self._games_in_buffer += 1

        # Flush if buffer is full
        if self._games_in_buffer >= self.chunk_size:
            self._flush_chunk()

    def _flush_chunk(self):
        """Write buffered training rows to a chunk file."""
        if not self._row_buffer:
            return

        chunk_name = f'chunk_{self._chunk_idx:04d}'
        if self.require_parquet:
            self._write_parquet_chunk(chunk_name)
        else:
            try:
                self._write_parquet_chunk(chunk_name)
            except (ImportError, Exception):
                self._write_jsonl_chunk(chunk_name)

        self._total_rows += len(self._row_buffer)
        self._row_buffer = []
        self._chunk_idx += 1
        self._games_in_buffer = 0

    def _write_parquet_chunk(self, chunk_name: str):
        """Write chunk as Parquet (requires pyarrow)."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = self._row_buffer
        for row in rows:
            for key in (
                'board_names',
                'board_stars',
                'trait_names',
                'trait_counts',
                'augments',
                'units',
                'traits',
                'opponent_units',
                'opponent_traits',
            ):
                if key in row and isinstance(row[key], (list, dict)):
                    row[key] = json.dumps(row[key])

        table = pa.Table.from_pylist(rows)
        path = os.path.join(self.output_dir, chunk_name + '.parquet')
        pq.write_table(table, path)

    def _write_jsonl_chunk(self, chunk_name: str):
        """Write chunk as JSON Lines (fallback)."""
        path = os.path.join(self.output_dir, chunk_name + '.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for row in self._row_buffer:
                f.write(json.dumps(row) + '\n')

    def write_checkpoint(self):
        """Write checkpoint for resume capability."""
        checkpoint = {
            'completed_seeds': sorted(self._completed_seeds),
            'num_completed': len(self._completed_seeds),
            'num_errors': len(self._errors),
            'chunks_written': self._chunk_idx,
            'total_rows': self._total_rows,
            'sum_game_time': self._sum_game_time,
            'total_rounds': self._total_rounds,
            'champ_placements': dict(self._champ_placements),
            'champ_placements_sq': dict(self._champ_placements_sq),
            'champ_counts': dict(self._champ_counts),
            'champ_top4_counts': dict(self._champ_top4_counts),
            'champ_win_counts': dict(self._champ_win_counts),
            'aug_placements': dict(self._aug_placements),
            'aug_placements_sq': dict(self._aug_placements_sq),
            'aug_counts': dict(self._aug_counts),
            'aug_top4_counts': dict(self._aug_top4_counts),
            'aug_win_counts': dict(self._aug_win_counts),
        }
        path = os.path.join(self.output_dir, 'checkpoint.json')
        # Write atomically (write to temp, then rename)
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f)
        os.replace(tmp_path, path)

    def finalize(self, total_time: float, num_workers: int,
                 run_metadata: Optional[Dict[str, Any]] = None) -> Dict:
        """Flush remaining data, write errors, summary, and final checkpoint."""
        self._flush_chunk()

        # Write errors
        if self._errors:
            error_path = os.path.join(self.output_dir, 'errors.json')
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(self._errors, f, indent=2)
            print(f"  Errors: {error_path} ({len(self._errors)} failures)")

        # Compute and write summary
        summary = self._compute_summary(total_time, num_workers, run_metadata or {})
        summary_path = os.path.join(self.output_dir, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"  Summary: {summary_path}")

        # Final checkpoint
        self.write_checkpoint()

        return summary

    def _compute_summary(self, total_time: float, num_workers: int,
                         run_metadata: Dict[str, Any]) -> Dict:
        """Compute aggregate statistics."""
        num_games = len(self._completed_seeds)
        if num_games == 0:
            return {
                'num_games': 0,
                'num_errors': len(self._errors),
                'total_time_sec': round(total_time, 1),
            }

        # Champion average placements
        champ_avg = {}
        for name in self._champ_counts:
            champ_avg[name] = round(self._champ_placements[name] / self._champ_counts[name], 2)
        aug_avg = {}
        for name in self._aug_counts:
            aug_avg[name] = round(self._aug_placements[name] / self._aug_counts[name], 2)

        top_champs = sorted(champ_avg.items(), key=lambda x: x[1])[:20]
        bot_champs = sorted(champ_avg.items(), key=lambda x: x[1], reverse=True)[:20]
        top_augs = sorted(aug_avg.items(), key=lambda x: x[1])[:20]

        def _build_rate_rows(names: List[str], counts: Counter, placements: Counter,
                             placements_sq: Counter, top4_counts: Counter,
                             win_counts: Counter) -> List[Dict[str, Any]]:
            rows = []
            for name in names:
                n = int(counts[name])
                if n <= 0:
                    continue
                avg = placements[name] / n
                mean_sq = placements_sq[name] / n
                variance = max(0.0, mean_sq - (avg * avg))
                std_dev = math.sqrt(variance)

                top4 = int(top4_counts[name])
                wins = int(win_counts[name])
                top4_rate = top4 / n
                win_rate = wins / n
                top4_low, top4_high = _wilson_interval(top4, n)
                win_low, win_high = _wilson_interval(wins, n)

                rows.append({
                    'name': name,
                    'samples': n,
                    'avg_placement': round(avg, 3),
                    'placement_stddev': round(std_dev, 3),
                    'top4_rate': round(top4_rate, 4),
                    'top4_ci95': [round(top4_low, 4), round(top4_high, 4)],
                    'win_rate': round(win_rate, 4),
                    'win_ci95': [round(win_low, 4), round(win_high, 4)],
                })
            return rows

        champion_metric_rows = _build_rate_rows(
            [name for name, _ in self._champ_counts.most_common(30)],
            self._champ_counts,
            self._champ_placements,
            self._champ_placements_sq,
            self._champ_top4_counts,
            self._champ_win_counts,
        )
        augment_metric_rows = _build_rate_rows(
            [name for name, _ in self._aug_counts.most_common(30)],
            self._aug_counts,
            self._aug_placements,
            self._aug_placements_sq,
            self._aug_top4_counts,
            self._aug_win_counts,
        )

        return {
            'num_games': num_games,
            'num_errors': len(self._errors),
            'num_workers': num_workers,
            'total_time_sec': round(total_time, 1),
            'games_per_sec': round(num_games / total_time, 2) if total_time > 0 else 0,
            'avg_game_time_sec': round(self._sum_game_time / num_games, 3),
            'avg_rounds': round(self._total_rounds / num_games, 1),
            'total_training_rows': self._total_rows,
            'total_chunks': self._chunk_idx,
            'top_champions': top_champs,
            'bottom_champions': bot_champs,
            'top_augments': top_augs,
            'champion_pick_rates': dict(self._champ_counts.most_common(20)),
            'confidence_method': 'wilson_95',
            'champion_metrics': sorted(champion_metric_rows, key=lambda x: x['avg_placement'])[:20],
            'augment_metrics': sorted(augment_metric_rows, key=lambda x: x['avg_placement'])[:20],
            'run_config': run_metadata,
        }


# ── Worker Init ──────────────────────────────────────────────────────────

def _worker_init():
    """Worker process initializer - pre-loads shared data."""
    from simulator.core.combat_engine import CombatEngine
    CombatEngine()  # Warm the cache


# ── Batch Runner ─────────────────────────────────────────────────────────

def run_batch(
    num_games: int,
    num_workers: int,
    output_dir: str,
    seed_start: int = 0,
    agent_mix: Optional[Dict] = None,
    chunk_size: int = 100,
    resume: bool = False,
    agent_profile: str = 'random',
    checkpoint_every: Optional[int] = None,
    progress_every: Optional[int] = None,
    max_errors: Optional[int] = None,
    require_parquet: bool = False,
) -> Dict:
    """Run num_games in parallel with streaming output and checkpoints.

    Args:
        num_games: Total number of games to simulate.
        num_workers: Number of parallel worker processes.
        output_dir: Directory to write results to.
        seed_start: Starting seed (games use seeds seed_start..seed_start+num_games-1).
        agent_mix: Agent type distribution, e.g. {'random': 50, 'econ': 30, 'slam': 20}.
        chunk_size: Number of games per output chunk (controls memory usage).
        resume: If True, resume from existing checkpoint in output_dir.
        agent_profile: Agent profile name used for this run.
        checkpoint_every: Number of completed tasks between checkpoints.
        progress_every: Number of completed tasks between progress prints.
        max_errors: Stop run early after this many per-game errors.
        require_parquet: Fail output writes if parquet cannot be written.

    Returns:
        Summary dict with timing and aggregate stats.
    """
    # Load checkpoint if resuming
    resume_state = None
    completed_seeds = set()
    if resume:
        checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                resume_state = json.load(f)
            completed_seeds = set(resume_state.get('completed_seeds', []))
            print(f"Resuming from checkpoint: {len(completed_seeds)} games already done")
        else:
            print("No checkpoint found, starting fresh")

    if require_parquet and not _pyarrow_available():
        raise RuntimeError(
            "require_parquet was set but pyarrow is unavailable. "
            "Install pyarrow or remove --require-parquet."
        )

    os.makedirs(output_dir, exist_ok=True)
    writer = StreamingWriter(
        output_dir,
        chunk_size=chunk_size,
        resume_state=resume_state,
        require_parquet=require_parquet,
    )

    # Build task list, skipping completed seeds
    all_seeds = [seed_start + i for i in range(num_games)]
    tasks = [(i, s, agent_mix) for i, s in enumerate(all_seeds)
             if s not in completed_seeds]
    remaining = len(tasks)

    if remaining == 0:
        print("All games already completed!")
        return writer.finalize(
            0.0,
            num_workers,
            run_metadata={
                'seed_start': seed_start,
                'seed_end': seed_start + num_games - 1,
                'agent_profile': agent_profile,
                'agent_mix': agent_mix if agent_mix else {'random': 100},
                'chunk_size': chunk_size,
                'resume': resume,
                'checkpoint_every': checkpoint_every,
                'progress_every': progress_every,
                'max_errors': max_errors,
                'require_parquet': require_parquet,
                'aborted': False,
                'aborted_reason': None,
            },
        )

    agent_desc = 'default (fast_random)' if not agent_mix else str(agent_mix)
    print(f"Running {remaining} games across {num_workers} workers "
          f"(chunk_size={chunk_size})")
    print(f"Seeds: {seed_start} to {seed_start + num_games - 1} "
          f"({len(completed_seeds)} already done)")
    print(f"Agents: {agent_desc}")
    print(f"Output: {output_dir}")
    print()

    start = time.perf_counter()
    checkpoint_interval = checkpoint_every if checkpoint_every and checkpoint_every > 0 else max(1, remaining // 20)
    progress_interval = progress_every if progress_every and progress_every > 0 else max(1, remaining // 10)
    done = 0
    aborted_reason: Optional[str] = None

    def _process_result(result):
        nonlocal done
        writer.add_result(result)
        done += 1
        if done % progress_interval == 0 or done == remaining:
            elapsed = time.perf_counter() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (remaining - done) / rate if rate > 0 else 0
            err_str = f", {writer.num_errors} errors" if writer.num_errors else ""
            print(f"  [{done}/{remaining}] {rate:.1f} games/sec, "
                  f"ETA: {eta:.0f}s{err_str}")

        if max_errors is not None and writer.num_errors >= max_errors:
            raise BatchAbort(f"Reached max error threshold ({writer.num_errors}/{max_errors}).")

        if done % checkpoint_interval == 0:
            writer.write_checkpoint()

    if num_workers <= 1:
        # Sequential mode
        _worker_init()
        try:
            for task in tasks:
                result = run_game(task)
                _process_result(result)
        except BatchAbort as exc:
            aborted_reason = str(exc)
    else:
        # Parallel mode
        with multiprocessing.Pool(num_workers, initializer=_worker_init) as pool:
            chunksize = max(1, remaining // (num_workers * 4))
            try:
                for result in pool.imap_unordered(run_game, tasks, chunksize=chunksize):
                    _process_result(result)
            except BatchAbort as exc:
                aborted_reason = str(exc)
                pool.terminate()

    total_time = time.perf_counter() - start
    if aborted_reason:
        print(f"\nRun aborted early: {aborted_reason}")
        print(f"Processed {done}/{remaining} tasks before stop.")
    else:
        print(f"\nAll {remaining} games completed in {total_time:.1f}s "
              f"({remaining / total_time:.1f} games/sec)")
    if writer.num_errors:
        print(f"  {writer.num_errors} games failed (see errors.json)")

    writer.write_checkpoint()
    print("Writing final results...")
    summary = writer.finalize(
        total_time,
        num_workers,
        run_metadata={
            'seed_start': seed_start,
            'seed_end': seed_start + num_games - 1,
            'agent_profile': agent_profile,
            'agent_mix': agent_mix if agent_mix else {'random': 100},
            'chunk_size': chunk_size,
            'resume': resume,
            'checkpoint_every': checkpoint_interval,
            'progress_every': progress_interval,
            'max_errors': max_errors,
            'require_parquet': require_parquet,
            'aborted': bool(aborted_reason),
            'aborted_reason': aborted_reason,
        },
    )
    return summary


# ── CLI ──────────────────────────────────────────────────────────────────

def _parse_agent_mix(s: str) -> Dict[str, int]:
    """Parse agent mix string like 'random:50,econ:30,slam:20'."""
    mix = {}
    for part in s.split(','):
        name, weight = part.strip().split(':')
        name = name.strip()
        if name not in ('random', 'econ', 'slam'):
            raise ValueError(f"Unknown agent type '{name}'. "
                             f"Valid types: random, econ, slam")
        parsed_weight = int(weight.strip())
        if parsed_weight < 0:
            raise ValueError(f"Weight for '{name}' cannot be negative")
        mix[name] = parsed_weight
    if not mix or sum(mix.values()) <= 0:
        raise ValueError("Agent mix must include at least one positive weight")
    return mix


def main():
    parser = argparse.ArgumentParser(
        description='Run batch TFT game simulations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Quick test:       python -m simulator.cloud_runner --games 10 --workers 1
  Production run:   python -m simulator.cloud_runner --games 10000 --workers 8 --output results/run_001
  Resume crashed:   python -m simulator.cloud_runner --games 10000 --resume results/run_001
  Mixed agents:     python -m simulator.cloud_runner --games 1000 --agent-mix random:50,econ:30,slam:20
  Ladder profile:   python -m simulator.cloud_runner --games 1000 --agent-profile ladder
  Large scale:      python -m simulator.cloud_runner --games 100000 --chunk-size 500
        """,
    )
    parser.add_argument('--games', type=int, default=10,
                        help='Number of games to simulate')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of parallel workers (default: CPU count - 1)')
    parser.add_argument('--output', type=str, default='results/batch',
                        help='Output directory for results')
    parser.add_argument('--seed-start', type=int, default=0,
                        help='Starting seed for deterministic runs')
    parser.add_argument('--agent-mix', type=str, default=None,
                        help='Agent type distribution, e.g. "random:50,econ:30,slam:20"')
    parser.add_argument('--agent-profile', type=str, default='random',
                        choices=sorted(AGENT_PROFILES.keys()),
                        help='Preset agent behavior profile used when --agent-mix is not provided')
    parser.add_argument('--chunk-size', type=int, default=100,
                        help='Games per output chunk (controls memory usage)')
    parser.add_argument('--resume', type=str, default=None, metavar='DIR',
                        help='Resume an interrupted batch from checkpoint in DIR')
    parser.add_argument('--checkpoint-every', type=int, default=None,
                        help='Write checkpoint every N completed tasks')
    parser.add_argument('--progress-every', type=int, default=None,
                        help='Print progress every N completed tasks')
    parser.add_argument('--max-errors', type=int, default=None,
                        help='Stop run early after N game errors')
    parser.add_argument('--require-parquet', action='store_true',
                        help='Fail run if parquet output is unavailable')
    parser.add_argument('--skip-reference-validation', action='store_true',
                        help='Skip simulator reference preflight validation')
    args = parser.parse_args()

    num_workers = args.workers or max(1, multiprocessing.cpu_count() - 1)

    if not args.skip_reference_validation:
        try:
            _validate_reference_data_preflight()
        except RuntimeError as exc:
            print(str(exc))
            sys.exit(1)

    # Handle resume mode
    if args.resume:
        output_dir = args.resume
        # Load checkpoint to get original settings
        checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
        if not os.path.exists(checkpoint_path):
            print(f"Error: No checkpoint.json found in {output_dir}")
            sys.exit(1)
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        summary = run_batch(
            num_games=args.games,
            num_workers=num_workers,
            output_dir=output_dir,
            seed_start=args.seed_start,
            agent_mix=agent_mix,
            chunk_size=args.chunk_size,
            resume=True,
            agent_profile=args.agent_profile,
            checkpoint_every=args.checkpoint_every,
            progress_every=args.progress_every,
            max_errors=args.max_errors,
            require_parquet=args.require_parquet,
        )
    else:
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        summary = run_batch(
            num_games=args.games,
            num_workers=num_workers,
            output_dir=args.output,
            seed_start=args.seed_start,
            agent_mix=agent_mix,
            chunk_size=args.chunk_size,
            agent_profile=args.agent_profile,
            checkpoint_every=args.checkpoint_every,
            progress_every=args.progress_every,
            max_errors=args.max_errors,
            require_parquet=args.require_parquet,
        )

    print(f"\n{'='*50}")
    print(f"BATCH COMPLETE")
    print(f"{'='*50}")
    print(f"Games:  {summary.get('num_games', 0)}")
    print(f"Errors: {summary.get('num_errors', 0)}")
    print(f"Time:   {summary.get('total_time_sec', 0)}s")
    print(f"Rate:   {summary.get('games_per_sec', 0)} games/sec")
    print(f"Rows:   {summary.get('total_training_rows', 0)}")
    print(f"Chunks: {summary.get('total_chunks', 0)}")

    if summary.get('top_champions'):
        print(f"\nTop 5 champions (avg placement):")
        for name, avg in summary['top_champions'][:5]:
            print(f"  {name}: {avg}")
    if summary.get('bottom_champions'):
        print(f"\nBottom 5 champions (avg placement):")
        for name, avg in summary['bottom_champions'][:5]:
            print(f"  {name}: {avg}")


if __name__ == '__main__':
    main()

