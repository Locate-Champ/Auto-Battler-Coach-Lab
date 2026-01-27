# MetaTFT Log Data Extraction Guide

## Overview

MetaTFT uses Overwolf's Game Events Provider (GEP) API to capture live TFT game data. We can extract this data by monitoring their log files at:

```
C:\Users\<USER>\AppData\Local\Overwolf\Log\Apps\MetaTFT\
```

## How MetaTFT Gets Game Data

### 1. Overwolf GEP Features Registered

From `background.html.log` line 269:
```json
{
  "success": true,
  "supportedFeatures": [
    "gep_internal",
    "augments",
    "match_info",
    "me",
    "roster",
    "store",
    "board",
    "bench",
    "carousel"
  ]
}
```

### 2. Custom Plugin

MetaTFT also uses a custom plugin called `metatft-plugin` for additional memory reading:
- `tft_scoreboard` - Player scoreboard data
- `tft_shop` - Shop contents

## Data Available in Logs

### Augment Armory (Real-time augment choices)
**File:** `background.html.log`
```json
{"augment_options":["TFT_Augment_SpeedyDoubleKill","TFT_Augment_SavingsAccount","TFT11_Augment_Prizefighter"],"armory_state":"active","armory_type":"regular"}
```

### Item Selection (Darkin items, carousel, etc.)
**File:** `background.html.log` and `augment_recommendations.html.*.log`
```json
{"item_1":{"name":"TFT16_TheDarkinAegis"}, "item_2":{"name":"TFT16_TheDarkinScythe"}, "item_3":{"name":"TFT16_TheDarkinBow"}, "item_4":{"name":"TFT16_TheDarkinStaff"}}
```

### Stage/Round Events
**File:** `background.html.log`
```
[EVT] stage: 2-1
New Stage: "2-1"
```

### XP Tracking
**File:** `background.html.log`
```
XP: 0/6 -> 2/6
XP: 2/6 -> 0/10
```

### Player Health
**File:** `background.html.log`
```
Correcting health for player: EMoney13 93 100
Correcting health for player: Krad 94 100
```

### Scouting (Board viewing)
**File:** `background.html.log`
```
Scouting: Baccarat
Scouting: Ace
Scouting: Hysteria
```

### Win Chance Prediction (ML Model)
**File:** `win_chance.html.log`
```
WinChanceNumber: ~96%
WinChanceNumber: ~38%
WinChanceNumber: ~44%
```

### Bilgewater/Artifact Items
**File:** `augment_recommendations.html.*.log`
```json
{"item_1":{"name":"TFT16_Item_Bilgewater_HealthTier1"},"item_2":{"name":"TFT16_Item_Bilgewater_ASTier2"},"item_3":{"name":"TFT16_Item_Bilgewater_ShopRefresh"}}
```

## Key Log Files to Monitor

| File Pattern | Data Type |
|-------------|-----------|
| `background.html.log` | Main game events, stage changes, augments, health |
| `win_chance.html.log` | ML win predictions |
| `augment_recommendations.html.*.log` | Augment/item selection events |
| `matchups_map.html.log` | Matchup tracking |
| `ingamecontroller.html.*.log` | UI state, window positions |

## Implementation Strategy

### Option 1: File Watcher (Simplest)

Create a Python/Node script that:
1. Watches the MetaTFT log directory for changes
2. Parses new log lines as they're appended
3. Extracts JSON data payloads
4. Exposes via local WebSocket/HTTP for your overlay

```python
import os
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogHandler(FileSystemEventHandler):
    def __init__(self):
        self.file_positions = {}

    def on_modified(self, event):
        if event.src_path.endswith('.log'):
            self.process_log(event.src_path)

    def process_log(self, path):
        pos = self.file_positions.get(path, 0)
        with open(path, 'r', encoding='utf-8-sig') as f:
            f.seek(pos)
            for line in f:
                self.parse_line(line)
            self.file_positions[path] = f.tell()

    def parse_line(self, line):
        # Look for JSON-like patterns
        if 'augment_options' in line:
            # Extract augment data
            pass
        elif '[EVT] stage:' in line:
            # Extract stage change
            pass
        elif 'WinChanceNumber:' in line:
            # Extract win prediction
            pass
```

### Option 2: Direct Overwolf GEP API

If you build an Overwolf app yourself, you can use the same GEP API:

```javascript
// Register for TFT game events
overwolf.games.events.setRequiredFeatures(
  ["gep_internal", "augments", "match_info", "me", "roster", "store", "board", "bench", "carousel"],
  (result) => {
    console.log("Features registered:", result);
  }
);

// Listen for game events
overwolf.games.events.onNewEvents.addListener((info) => {
  console.log("Game event:", info);
});

overwolf.games.events.onInfoUpdates2.addListener((info) => {
  console.log("Info update:", info);
});
```

## Data ID Formats

### Champions
- Format: `TFT16_<ChampionName>`
- Examples: `TFT16_Ekko`, `TFT16_Draven`, `TFT16_Bard`

### Augments
- Format: `TFT_Augment_<Name>` or `TFT<Set>_Augment_<Name>`
- Examples: `TFT_Augment_SpeedyDoubleKill`, `TFT7_Augment_ClutteredMind`

### Items
- Standard: `TFT_Item_<Name>`
- Set-specific: `TFT16_<ItemName>` (e.g., Darkin items)
- Bilgewater: `TFT16_Item_Bilgewater_<Name>`

### Queue IDs
```
1090 - TFT Normal
1091 - TFT Ranked (Solo/Duo)
1092 - TFT Ranked (Flex)
1100 - TFT Ranked
1130 - TFT Hyper Roll
1160 - TFT Double Up
1170 - TFT Lab
1180 - TFT Remix Rumble
1210 - TFT Remix
6000 - TFT Arena
6110 - TFT Arena Ranked
6120 - TFT Arena Double Up
```

## MetaTFT API Endpoints (Public)

These APIs are used by MetaTFT for stat lookups:

```
# Unit items data
https://api-hc.metatft.com/tft-comps-api/unit_items_processed

# Unit details
https://api-hc.metatft.com/tft-stat-api/unit_detail?queue=1100&patch=current&unit=TFT16_Ekko

# Games played stats
https://api-hc.metatft.com/tft-stat-api/games?days=7

# Player profile
https://api.metatft.com/public/profile/lookup_by_riotid/NA1/<Name>/<Tag>

# Set data lookups
https://data.metatft.com/lookups/TFTSet16_latest_en_us.json
```

## ML Model Details

MetaTFT uses a board strength prediction model:
- Model name: `WinRateModelImproved_BoardStrength_TFTSet16`
- Updates daily (timestamp in model name)
- Predicts win probability as percentage (e.g., "~97%")
- Considers: units, items, traits, levels, positioning

## Next Steps

1. **Create a log watcher service** that runs alongside TFT
2. **Parse and structure the data** into a clean format
3. **Expose via WebSocket** for real-time overlay updates
4. **Cache state** to reconstruct full game state from partial updates
