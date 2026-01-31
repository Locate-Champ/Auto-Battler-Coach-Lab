# Combat Engine Research Review + MetaTFT Live Data Gap Analysis

## 1) Research folder takeaways (high-signal summary)

### Common ground across the documents
- Multiple documents describe **targeting as primarily “closest enemy by hex distance”** and retargeting when a target dies, becomes untargetable, or is otherwise invalid. (See: *Champion Combat Behavior in TFT (Set 10+).pdf*.)
- Several documents assert **a hard attack speed cap of 5.0 attacks/sec** and emphasize a **tick-based simulation** (often 30Hz), with combat run as a state machine (AcquireTarget → MoveToTarget → AttackWindup → AttackResolve). (See: *TFT Combat Engine Spec_ Set 16.docx*, *tft_combat_engine_spec_no_citations.pdf*.)
- Documents consistently treat **data as authoritative for numeric stats** (champion base values, items, augments), while **engine behavior is inferred**, with explicit mention of simulator-derived assumptions and validation plans. (See: *tft_combat_engine_spec_no_citations.pdf*.)

### Notable divergences / open questions
- **Targeting tiebreaker**: one document states equal-distance targets are effectively random (distance-only), while another describes **role-based priority** (tanks > fighters > marksmen, etc.). This is a key conflict to resolve with tests. (See: *Champion Combat Behavior in TFT (Set 10+).pdf* vs. *TFT Combat Mechanics_ The Complete Technical Breakdown.pdf*.)
- **Chase/retarget behavior**: one doc mentions a “1-hex chase limit” while another implies a longer pursuit window before retarget. This impacts positioning logic and should be verified. (See: *TFT Combat Mechanics_ The Complete Technical Breakdown.pdf* vs. *Champion Combat Behavior in TFT (Set 10+).pdf*.)
- **Set-16 specific mechanics** like role-based mana generation, unlockables, and updated CC/cast queue behavior are documented, but many timings/thresholds are marked inferred. (See: *research-Technical Combat Engine Specification for Teamfight Tactics (Current Set and Patch).docx*.)

### Practical reading on “what matters for a simulator”
The strongest throughline is “**be data-driven for numbers, and isolate engine timing/state transitions for testing**.” The specs repeatedly emphasize pulling current set data (CommunityDragon/Riot) and treating engine timing as a separable layer that can be verified with small, controlled experiments.

---

## 2) What live MetaTFT data we already collect (post-injection)

### Redux injection path (live state)
The injected Redux bridge script pulls:
- **Board/bench/shop/carousel** pieces,
- **Player info** (gold/health/xp/rank/name),
- **Roster** (all 8 players’ statuses),
- **Match + game metadata**,
- **All 8 boards (board_data)**,
then emits it over WebSocket to the backend. (See: `app/redux_bridge/inject.js`.)

### Backend handling
The handler:
- Normalizes board and bench units (including stars/items/positions),
- Parses player info, roster, and opponent boards,
- Stores the raw payload for future use, and
- Feeds the state into the main state manager. (See: `app/redux_bridge/handler.py`.)

### Log watcher path (Overwolf log files)
The log watcher:
- Monitors MetaTFT’s Overwolf log directory for log file updates,
- Parses lines into structured events for **stage/xp/health**, **augment armories**, **item selection**, **win chance**, **board/bench/roster snapshots**, and **game start**,
- Emits those events to update the state manager. (See: `app/watcher/log_watcher.py`, `app/watcher/parser.py`, `app/config.py`.)

### Separate augment parser
There’s an augment log parser that scans augment recommendation logs, extracts options + selections, and can export them as CSV. (See: `src/metatft_parser.py`.)

---

## 3) Can live MetaTFT data fill combat engine gaps?

### What it *can* fill reliably
- **Ground truth state inputs** for simulation: board positions, star levels, items, traits/roster context, shop state, player health/gold/xp, augment selections. This is valuable for **initial conditions** and **mid-round state snapshots**.
- **Macro timeline anchors**: stage changes, game start, win chance signals, and health deltas can help anchor the **phase timeline** and validate “round flow” assumptions.
- **Validation datasets**: repeated snapshots can be used to verify predictions from a simulated combat engine (e.g., at least at the “outcome probability” or “win chance” layer).

### What it *cannot* fill (from current logs + redux snapshots)
- **Per-tick combat resolution**: targeting switches, attack windups, projectile travel, on-hit timing, damage calculation order, and CC timing are not directly logged.
- **Deterministic internal engine timings**: even if Redux updates are frequent, they are not a reliable substitute for the engine’s 30Hz combat tick and do not include granular attack/cast events.
- **Precise target selection rules**: logs show board state but not *why* a given unit chose a target; this needs focused experiments, simulator inspection, or frame-by-frame video analysis.

### Bottom line
MetaTFT live data **helps validate and parameterize** the combat engine (initial conditions + macro outputs) but **does not close the engine mechanics gaps** on its own. The highest-value use is to instrument a **state snapshot pipeline** and use it to **compare simulated vs. observed outcomes**, not to infer micro-timings directly.

---

## 4) What I would do next (actionable plan)

1. **Unify the ingestion pipeline**
   - Persist the Redux snapshot stream (including `raw`) alongside parsed log events so we can align them by timestamp.
   - Build a simple “round timeline” from stage changes + health deltas + win chance to segment combat windows.

2. **Augment snapshot richness**
   - Verify if Redux state exposes **traits, buffs, or combat flags** and add them to the payload. If not present, pull them from static data and infer via roster.
   - Ensure every unit snapshot includes **full item list + star level + position** and cross-reference with roster to derive active traits.

3. **Use live data to validate, not infer**
   - Run the simulator on snapshot inputs and compare the predicted outcome with the observed win chance / result.
   - Where predictions drift, flag those fights as “mechanics unknowns” for deeper manual investigation.

4. **Targeted micro-tests for unresolved mechanics**
   - Create a small “test harness” board setup (1v1 or 2v2) and record video at high frame rate to verify target priority and chase/retarget behavior.
   - Use the docs’ proposed test plans (when present) to resolve the specific conflicts (role priority vs. random tiebreakers).

---

## 5) Recommendation (synthesis)
Use MetaTFT live data to **anchor state and validate outcomes**, while treating **engine timing and targeting as a separate, experimentally validated layer**. The research folder gives a solid working model, but conflicting claims (especially target tiebreakers and chase limits) require deliberate tests. The fastest path forward is to build a **snapshot + simulation comparison loop** and let disagreements guide targeted combat micro-tests.

---

## 6) Direct answer: “Can we get combat data after injecting the script?”
Short answer: **not per-tick combat resolution**. The injected Redux bridge provides high-level state snapshots (board/bench/shop/carousel, player/roster, match/game info, and opponent board data), but it does **not** expose per-attack events, target selection decisions, damage application order, or timing signals at combat tick granularity. That means you can capture **combat-relevant inputs** and some **macro outputs**, but not the internal combat event stream itself. (See: `app/redux_bridge/inject.js`, `app/redux_bridge/handler.py`.)

If you need real combat telemetry, the options are:
- add a **combat-event instrumentation layer** inside the game client (not feasible here), or
- build a **snapshot + outcome validation loop** (recommended), or
- run **targeted micro-tests** with video/frame capture to resolve the remaining mechanics ambiguities.

---

## 7) Commands/tools already in the repo for log extraction and sync
If by “commands I extracted” you mean the existing utilities for collecting MetaTFT logs, these are the relevant files and their behaviors:

- `scripts/watch_logs.py` watches MetaTFT log files on Windows and can optionally auto-sync the logs into the repo. It also prints detected match UUIDs and the corresponding data URL. (Run: `python scripts/watch_logs.py --uuid` or `--sync`.)
- `scripts/quick_sync.bat` copies the MetaTFT log files (`background.html.log`, `main.html.log`, `ingamedesktop.html.log`) into a target folder in the repo.
- `scripts/sync_metatft.py` discovers the MetaTFT log directory, parses augment logs via `MetaTFTLogParser`, and can run in a watch mode to keep syncing new logs.
- `scripts/parse_large_metatft_log.py` streams very large log files and emits JSONL event records using the same regex patterns as the live log watcher. (Run: `python scripts/parse_large_metatft_log.py --input <logfile> --output outputs/metatft_events.jsonl`.)
- `scripts/extract_network_commands.py` scans log files for HTTP URLs or method+URL patterns and emits a JSONL list of network-like commands. (Run: `python scripts/extract_network_commands.py --input <logfile-or-dir> --output outputs/metatft_network_commands.jsonl`.)
- `app/redux_bridge/inject_network.js` injects into MetaTFT DevTools to log fetch/XHR/WebSocket commands to console, `window.__tftCoachNetworkLog`, and stream JSONL logs to `ws://127.0.0.1:8765/network-log` (written to `outputs/network_logs/` by the backend).

These are the command-level entry points currently present for extraction and syncing; if you want a unified CLI, I would consolidate them and make the output schema consistent across Redux snapshots + log events.

---

## Appendix: commands used during review
- `rg -n "metatft" -S`
- `sed -n '1,200p' app/redux_bridge/inject.js`
- `sed -n '1,200p' app/redux_bridge/handler.py`
- `sed -n '1,220p' app/watcher/log_watcher.py`
- `sed -n '1,240p' app/watcher/parser.py`
- `sed -n '1,240p' src/metatft_parser.py`
- `python - <<'PY' ...` (text extraction from the research PDFs/DOCX)
- `nl -ba outputs/combat_engine_research_report.md`
- `nl -ba scripts/extract_network_commands.py`
- `nl -ba app/redux_bridge/inject_network.js`
- `nl -ba app/server/websocket.py`
