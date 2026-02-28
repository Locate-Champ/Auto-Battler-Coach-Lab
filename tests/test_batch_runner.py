"""Integration tests for BatchRunner (Phase 8 - GLBL-01)."""

from __future__ import annotations

import os

import pytest

from simulator.cloud_runner import BatchRunner, BatchRunnerConfig


class TestBatchRunnerConfig:
    """Unit tests for BatchRunnerConfig frozen dataclass."""

    def test_config_is_frozen(self):
        config = BatchRunnerConfig(num_games=2, num_workers=1, output_dir="/tmp/test")
        with pytest.raises(AttributeError):
            config.num_games = 99  # type: ignore[misc]

    def test_config_field_count(self):
        """Config must have all run_batch() params as fields."""
        import dataclasses

        fields = dataclasses.fields(BatchRunnerConfig)
        # At minimum: num_games, num_workers, output_dir + 28 optional fields
        assert len(fields) >= 31

    def test_config_defaults(self):
        config = BatchRunnerConfig(num_games=10, num_workers=2, output_dir="/tmp/test")
        assert config.engine == "python"
        assert config.seed_start == 0
        assert config.chunk_size == 100
        assert config.resume is False

    def test_config_replace(self):
        """dataclasses.replace() works for test overrides."""
        import dataclasses

        config = BatchRunnerConfig(num_games=10, num_workers=2, output_dir="/tmp/test")
        modified = dataclasses.replace(config, num_games=20)
        assert modified.num_games == 20
        assert config.num_games == 10  # original unchanged


class TestBatchRunnerSequential:
    """Integration tests for BatchRunner sequential mode (1 worker)."""

    def test_sequential_run_produces_summary(self, tmp_path):
        """BatchRunner with 1 worker completes and returns valid summary."""
        config = BatchRunnerConfig(
            num_games=2,
            num_workers=1,
            output_dir=str(tmp_path / "seq"),
            engine="python",
            seed_start=42,
            progress_every=1,
        )
        summary = BatchRunner(config).run()
        assert summary["num_games"] == 2
        assert summary["num_errors"] == 0
        assert summary["total_time_sec"] > 0
        assert os.path.isdir(str(tmp_path / "seq"))

    def test_sequential_deterministic_seeds(self, tmp_path):
        """Same seeds produce consistent game counts."""
        config = BatchRunnerConfig(
            num_games=2,
            num_workers=1,
            output_dir=str(tmp_path / "det"),
            engine="python",
            seed_start=0,
            progress_every=1,
        )
        s1 = BatchRunner(config).run()
        # Re-run with same config, different output dir
        import dataclasses

        config2 = dataclasses.replace(config, output_dir=str(tmp_path / "det2"))
        s2 = BatchRunner(config2).run()
        assert s1["num_games"] == s2["num_games"]


class TestBatchRunnerParallel:
    """Integration tests for BatchRunner parallel mode (spawn Pool)."""

    def test_parallel_spawn_pool(self, tmp_path):
        """BatchRunner with 2 workers uses spawn Pool and completes."""
        config = BatchRunnerConfig(
            num_games=4,
            num_workers=2,
            output_dir=str(tmp_path / "par"),
            engine="python",
            seed_start=0,
            progress_every=1,
        )
        summary = BatchRunner(config).run()
        assert summary["num_games"] == 4
        assert summary["num_errors"] == 0


class TestBatchRunnerIsolation:
    """Integration tests proving two BatchRunner instances don't share state."""

    def test_two_runners_independent(self, tmp_path):
        """Two BatchRunner instances with different configs produce independent results."""
        config_a = BatchRunnerConfig(
            num_games=2,
            num_workers=1,
            output_dir=str(tmp_path / "a"),
            engine="python",
            seed_start=0,
            progress_every=1,
        )
        config_b = BatchRunnerConfig(
            num_games=3,
            num_workers=1,
            output_dir=str(tmp_path / "b"),
            engine="python",
            seed_start=100,
            progress_every=1,
        )
        summary_a = BatchRunner(config_a).run()
        summary_b = BatchRunner(config_b).run()
        # Different game counts -> independent
        assert summary_a["num_games"] == 2
        assert summary_b["num_games"] == 3
        # Both completed without error
        assert summary_a["num_errors"] == 0
        assert summary_b["num_errors"] == 0
        # Output dirs are separate
        assert os.path.isdir(str(tmp_path / "a"))
        assert os.path.isdir(str(tmp_path / "b"))

    def test_no_main_process_globals(self):
        """Module-level _RUST_FULL_SIMULATOR and _RUST_PARQUET_API_VALIDATED
        no longer exist as main-process mutable globals."""
        from simulator import cloud_runner

        # Old globals should not exist
        assert not hasattr(cloud_runner, "_RUST_FULL_SIMULATOR"), (
            "_RUST_FULL_SIMULATOR should be removed from module level"
        )
        assert not hasattr(cloud_runner, "_RUST_PARQUET_API_VALIDATED"), (
            "_RUST_PARQUET_API_VALIDATED should be removed from module level"
        )
        # New worker-local globals should exist (they are process-local, set by initializer)
        assert hasattr(cloud_runner, "_worker_sim")
        assert hasattr(cloud_runner, "_worker_parquet_validated")
