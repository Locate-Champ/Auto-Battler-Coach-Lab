<#
Run a lightweight verification suite based on what changed in git.

Examples:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode changed -Plan
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode changed
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode all
#>

param(
    [ValidateSet("changed", "all")]
    [string]$Mode = "changed",

    [switch]$Plan,

    [switch]$CoachEvalGate,

    [int]$ValidateOutputGames = 30,

    [int]$ValidateOutputWorkers = 1
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Exe,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$ArgList
    )

    $joined = ($ArgList | ForEach-Object { $_ }) -join " "
    Write-Host ("[RUN] {0} {1}" -f $Exe, $joined)
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed with exit code {0}: {1} {2}" -f $LASTEXITCODE, $Exe, $joined)
    }
}

function Get-RepoRoot {
    $root = Resolve-Path (Join-Path $PSScriptRoot "..")
    return $root.Path
}

function Get-ChangedFiles {
    $files = @()

    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $git) {
        return @()
    }

    $files += (git diff --name-only)
    $files += (git diff --name-only --staged)

    $files = $files |
        Where-Object { $_ -and $_.Trim().Length -gt 0 } |
        ForEach-Object { $_.Trim() } |
        Sort-Object -Unique

    return ,$files
}

$repo_root = Get-RepoRoot
Push-Location $repo_root
try {
    $python_exe = "python"
    $venv_python_win = Join-Path $repo_root ".venv\\Scripts\\python.exe"
    $venv_python_posix = Join-Path $repo_root ".venv/bin/python"
    if (Test-Path $venv_python_win) {
        $python_exe = $venv_python_win
    } elseif (Test-Path $venv_python_posix) {
        $python_exe = $venv_python_posix
    }

    $changed = @()
    if ($Mode -eq "changed") {
        $changed = Get-ChangedFiles
    }

    if ($Mode -eq "changed" -and $changed.Count -eq 0 -and -not $CoachEvalGate) {
        Write-Host "[OK] No staged/unstaged changes detected via git; nothing to verify."
        exit 0
    }

    $run_pytest = $false
    $run_benchmark = $false
    $run_validate_output = $false
    $run_frontend_build = $false
    $run_coach_eval_gate = $false

    if ($Mode -eq "all") {
        $run_pytest = $true
        $run_benchmark = $true
        $run_validate_output = $true
        $run_frontend_build = $true
        $run_coach_eval_gate = $true
    } else {
        $docs_only = $true
        foreach ($path in $changed) {
            if ($path -match "\.(md|txt)$") {
                continue
            }
            $docs_only = $false
            break
        }

        if ($docs_only -and -not $CoachEvalGate) {
            Write-Host "[OK] Only documentation changes detected; skipping checks."
            exit 0
        }

        $run_pytest = ($changed | Where-Object { $_ -match "\.py$" }).Count -gt 0

        $run_benchmark = (
            $changed |
                Where-Object { $_ -match "^simulator/(core|game)/" -or $_ -eq "simulator/benchmark.py" }
        ).Count -gt 0

        $run_validate_output = (
            $changed |
                Where-Object {
                    $_ -match "^simulator/game/" -or
                    $_ -in @(
                        "simulator/cloud_runner.py",
                        "simulator/validate_output.py",
                        "simulator/aggregate_results.py"
                    )
                }
        ).Count -gt 0

        $run_frontend_build = (
            $changed |
                Where-Object { $_ -match "^app/frontend/" -or $_ -match "\.(ts|tsx|css|html)$" }
        ).Count -gt 0

        $run_coach_eval_gate = $CoachEvalGate -or (
            $changed |
                Where-Object {
                    $_ -match "^coach/" -or
                    $_ -eq "app/server/websocket.py" -or
                    $_ -match "^tests/test_coach_"
                }
        ).Count -gt 0
    }

    Write-Host "[INFO] verify.ps1 plan"
    $pytest_label = if ($run_pytest) { "yes" } else { "no" }
    $benchmark_label = if ($run_benchmark) { "yes" } else { "no" }
    $validate_label = if ($run_validate_output) { "yes" } else { "no" }
    $frontend_label = if ($run_frontend_build) { "yes" } else { "no" }
    $coach_eval_label = if ($run_coach_eval_gate) { "yes" } else { "no" }

    Write-Host ("  pytest:              {0}" -f $pytest_label)
    Write-Host ("  simulator.benchmark: {0}" -f $benchmark_label)
    Write-Host ("  simulator.validate_output: {0}" -f $validate_label)
    Write-Host ("  frontend build:      {0}" -f $frontend_label)
    Write-Host ("  coach eval gate:     {0}" -f $coach_eval_label)

    if ($Plan) {
        exit 0
    }

    if ($run_pytest) {
        Invoke-Checked $python_exe "-m" "pytest"
    }

    if ($run_benchmark) {
        Invoke-Checked $python_exe "-m" "simulator.benchmark"
    }

    if ($run_validate_output) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $out_dir = Join-Path "results" ("tmp_verify_{0}" -f $timestamp)

        Invoke-Checked $python_exe "-m" "simulator.cloud_runner" "--games" "$ValidateOutputGames" "--workers" "$ValidateOutputWorkers" "--output" "$out_dir"
        Invoke-Checked $python_exe "-m" "simulator.validate_output" "$out_dir"
    }

    if ($run_frontend_build) {
        $frontend_dir = Join-Path $repo_root "app\\frontend"
        Push-Location $frontend_dir
        try {
            Invoke-Checked npm "run" "build"
        } finally {
            Pop-Location
        }
    }

    if ($run_coach_eval_gate) {
        $eval_set = Join-Path $repo_root "outputs\\coach\\eval_sets\\fixed_eval_set_opt_phase1_25.jsonl"
        $baseline = Join-Path $repo_root "outputs\\coach\\eval_reports\\fixed_baseline_opt_phase1_25.json"
        $current = Join-Path $repo_root "outputs\\coach\\eval_reports\\fixed_current_opt_phase1_25.json"

        if ((Test-Path $eval_set) -and (Test-Path $baseline)) {
            Invoke-Checked $python_exe "-m" "coach.offline.eval_coach" "--eval-set" "$eval_set" "--limit" "25" "--output" "$current" "--baseline-report" "$baseline"
        } else {
            Write-Host "[WARN] Coach eval gate skipped: missing fixed eval set and/or baseline report."
            Write-Host ("[WARN] Expected: {0}" -f $eval_set)
            Write-Host ("[WARN] Expected: {0}" -f $baseline)
        }
    }

    Write-Host "[OK] Verification complete."
    exit 0
} finally {
    Pop-Location
}
