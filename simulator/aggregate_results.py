"""Aggregate results from multiple batch runs.

Merges training data and analytics from separate batch output directories
into a unified dataset.

Usage:
    python -m simulator.aggregate_results results/run_001 results/run_002 --output results/merged
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def merge_summaries(input_dirs: List[str]) -> Dict:
    """Merge summary.json files from multiple batch runs."""
    total_games = 0
    total_time = 0.0
    total_rows = 0
    champ_totals = Counter()
    champ_counts = Counter()
    aug_totals = Counter()
    aug_counts = Counter()
    pick_counts = Counter()

    for d in input_dirs:
        summary_path = os.path.join(d, 'summary.json')
        if not os.path.exists(summary_path):
            print(f"  Skipping {d} (no summary.json)")
            continue

        with open(summary_path, 'r') as f:
            s = json.load(f)

        total_games += s['num_games']
        total_time += s['total_time_sec']
        total_rows += s['total_training_rows']

        # Merge champion data
        for name, avg in s.get('top_champions', []) + s.get('bottom_champions', []):
            count = s.get('champion_pick_rates', {}).get(name, 1)
            champ_totals[name] += avg * count
            champ_counts[name] += count
            pick_counts[name] += count

        # Also merge from pick rates for completeness
        for name, count in s.get('champion_pick_rates', {}).items():
            pick_counts[name] = max(pick_counts[name], count)

    # Compute merged averages
    champ_avg = {}
    for name in champ_counts:
        champ_avg[name] = round(champ_totals[name] / champ_counts[name], 2)

    top_champs = sorted(champ_avg.items(), key=lambda x: x[1])[:20]
    bot_champs = sorted(champ_avg.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        'total_games': total_games,
        'total_time_sec': round(total_time, 1),
        'total_training_rows': total_rows,
        'effective_rate': round(total_games / total_time, 2) if total_time > 0 else 0,
        'top_champions': top_champs,
        'bottom_champions': bot_champs,
        'champion_pick_rates': dict(pick_counts.most_common(30)),
    }


def merge_training_data(input_dirs: List[str], output_dir: str):
    """Merge training data files (JSON or Parquet)."""
    chunked_outputs = []
    for d in input_dirs:
        has_chunk = any(Path(d).glob('chunk_*.parquet')) or any(Path(d).glob('chunk_*.jsonl'))
        if has_chunk:
            chunked_outputs.append(d)
    if chunked_outputs:
        print("  Detected chunked shard outputs (chunk_*.parquet/jsonl).")
        print("  Skipping monolithic training-data merge in aggregate_results.")
        print("  Use models.data_loader.DataLoader on the shard root directory instead.")
        return

    # Try Parquet merge first
    parquet_files = []
    json_files = []
    for d in input_dirs:
        pq_path = os.path.join(d, 'training_data.parquet')
        js_path = os.path.join(d, 'training_data.json')
        if os.path.exists(pq_path):
            parquet_files.append(pq_path)
        elif os.path.exists(js_path):
            json_files.append(js_path)

    if parquet_files:
        try:
            import pyarrow.parquet as pq
            import pyarrow as pa

            tables = [pq.read_table(f) for f in parquet_files]

            # Also convert any JSON files
            for jf in json_files:
                with open(jf, 'r') as f:
                    rows = json.load(f)
                if rows:
                    tables.append(pa.Table.from_pylist(rows))

            if tables:
                merged = pa.concat_tables(tables)
                out_path = os.path.join(output_dir, 'training_data.parquet')
                pq.write_table(merged, out_path)
                print(f"  Merged training data: {out_path} ({len(merged)} rows)")
                return
        except ImportError:
            pass

    # Fallback: merge JSON files
    all_rows = []
    for jf in json_files:
        with open(jf, 'r') as f:
            all_rows.extend(json.load(f))
    for pf in parquet_files:
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(pf)
            all_rows.extend(table.to_pylist())
        except ImportError:
            print(f"  Warning: Cannot read {pf} without pyarrow")

    if all_rows:
        out_path = os.path.join(output_dir, 'training_data.json')
        with open(out_path, 'w') as f:
            json.dump(all_rows, f)
        print(f"  Merged training data: {out_path} ({len(all_rows)} rows)")


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate results from multiple batch runs'
    )
    parser.add_argument('input_dirs', nargs='+',
                        help='Input directories to merge')
    parser.add_argument('--output', type=str, default='results/merged',
                        help='Output directory for merged results')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print(f"Merging {len(args.input_dirs)} batch runs...")

    # Merge summaries
    summary = merge_summaries(args.input_dirs)
    summary_path = os.path.join(args.output, 'summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary: {summary_path}")

    # Merge training data
    merge_training_data(args.input_dirs, args.output)

    print(f"\nMerged results:")
    print(f"  Total games: {summary['total_games']}")
    print(f"  Total training rows: {summary['total_training_rows']}")
    print(f"  Effective rate: {summary['effective_rate']} games/sec")


if __name__ == '__main__':
    main()
