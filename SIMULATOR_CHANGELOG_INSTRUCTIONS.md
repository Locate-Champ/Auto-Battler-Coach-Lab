# Simulator Changelog Extraction -- Instructions

## What We're Doing
Extracting simulator-related insights from past AI conversation logs (Codex and Claude Code) covering the last 2 weeks, and compiling them into `SIMULATOR_CHANGELOG.md` in the repo root.

## Process
1. Work **one day at a time**, most recent first (started at Feb 20, working backwards)
2. For each day, scan ALL session files from both Codex and Claude Code
3. Extract only simulator-related content: improvements, run times, what was done, bugs, how to run it
4. Skip sessions from other projects (e.g. tennis-market-analysis) -- just note they exist
5. Append the day's findings to `SIMULATOR_CHANGELOG.md` above the `<!-- Next day will be added above this line -->` marker
6. Stop after each day and wait for user signal before continuing to the next day

## Session Log Locations

### Codex Sessions
- **Path:** `c:/Users/forre/.codex/sessions/2026/02/<DD>/`
- **Format:** JSONL files, one per session, named `rollout-<timestamp>-<uuid>.jsonl`
- **Date folders available:** 07, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20
- **Note:** Many sessions are for OTHER projects (tennis-market-analysis, scraping, etc.). Check CWD early in the file to filter.

### Claude Code Sessions
- **Path:** `c:/Users/forre/.claude/projects/e--VS-Code-Auto-Battler-Coach-Lab/`
- **Format:** JSONL files named `<uuid>.jsonl`, no date folders -- check timestamp in first line
- **Only 3 sessions exist** (all from Feb 20). Earlier days have no Claude Code sessions for this project.
- **Other project folders exist** but we only care about `e--VS-Code-Auto-Battler-Coach-Lab`

## What to Extract Per Day
For each relevant session, capture:
- What was done (features, fixes, refactors)
- Performance metrics (games/sec, throughput, benchmark times)
- Bugs found and fixed
- Commands used / how to run things
- AWS details (instances, costs, configs)
- Key commits referenced
- Tests created/passed

## Progress
| Date | Status |
|------|--------|
| Feb 20 | Done |
| Feb 19 | Done |
| Feb 18 | Done |
| Feb 17 | Done |
| Feb 16 | Done |
| Feb 15 | Done |
| Feb 14 | Done |
| Feb 13 | Done |
| Feb 12 | Pending |
| Feb 11 | Pending |
| Feb 10 | Pending |
| Feb 09 | Pending |
| Feb 07 | Pending |

## Output File
- **File:** `SIMULATOR_CHANGELOG.md` (repo root)
- **Format:** One `## February DD, 2026` section per day, most recent first
- **Marker:** New days inserted above `<!-- Next day will be added above this line -->`

## Tips for Agents
- Use `general-purpose` subagents to process large batches of session files in parallel
- Split into batches of ~6 files per agent to stay within context limits
- Read files in chunks (offset/limit) since some are 10MB+
- Identify project by checking CWD or file paths in the first ~100 lines of each session
- Look for keywords: simulator, combat, benchmark, game, runner, cloud_runner, performance, timing, workers, batch, determinism, champion, trait, shop, augment, item, round, stage, player, board, unlock, quest, ixtal, rayon, rust, parquet
