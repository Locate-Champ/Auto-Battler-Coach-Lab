from simulator import cloud_runner


def test_build_cost_telemetry_reports_round_and_cost_metrics() -> None:
    telemetry = cloud_runner._build_cost_telemetry(
        total_time_sec=3600.0,
        num_games=100,
        total_rounds=2500,
        num_workers=8,
        logical_cpu_count=16,
        instance_hourly_usd=0.5,
        cpu_utilization_samples_pct=[70.0, 80.0],
    )

    throughput = telemetry["throughput"]
    cpu = telemetry["cpu_utilization"]
    cost = telemetry["cost_estimate_usd"]

    assert throughput["games_per_sec"] == 0.0278
    assert throughput["rounds_per_sec"] == 0.6944
    assert throughput["sec_per_round"] == 1.44

    assert cpu["worker_share_pct_est"] == 50.0
    assert cpu["sample_count"] == 2
    assert cpu["sampled_avg_pct"] == 75.0

    assert cost["total_cost_usd"] == 0.5
    assert cost["usd_per_round"] == 0.0002
    assert cost["usd_per_1k_rounds"] == 0.2


def test_compute_summary_includes_cost_telemetry_for_completed_runs(tmp_path) -> None:
    writer = cloud_runner.StreamingWriter(str(tmp_path))
    writer._completed_seeds = [1, 2]
    writer._sum_game_time = 4.0
    writer._total_rounds = 20

    summary = writer._compute_summary(
        total_time=5.0,
        num_workers=4,
        run_metadata={
            "logical_cpu_count": 8,
            "instance_hourly_usd": 1.0,
            "cpu_utilization_samples_pct": [60.0],
        },
    )

    assert summary["num_games"] == 2
    assert summary["total_rounds"] == 20
    assert "cost_telemetry" in summary
    assert summary["cost_telemetry"]["throughput"]["rounds_per_sec"] == 4.0
    assert summary["cost_telemetry"]["cost_estimate_usd"]["total_cost_usd"] == 0.001389


def test_compute_summary_includes_cost_telemetry_for_empty_runs(tmp_path) -> None:
    writer = cloud_runner.StreamingWriter(str(tmp_path))

    summary = writer._compute_summary(
        total_time=0.0,
        num_workers=4,
        run_metadata={
            "logical_cpu_count": 8,
            "instance_hourly_usd": 0.0,
            "cpu_utilization_samples_pct": [],
        },
    )

    assert summary["num_games"] == 0
    assert summary["total_rounds"] == 0
    assert summary["cost_telemetry"]["throughput"]["rounds_per_sec"] == 0.0
