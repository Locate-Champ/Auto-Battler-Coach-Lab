# TFT Timing Calibration

Tools for measuring champion attack and spell timing from gameplay recordings.

## Setup

```bash
pip install opencv-python numpy yt-dlp
```

## Quick Start: YouTube Method (Recommended)

The fastest way to get timing data for rare champions (5-costs, etc.):

```bash
# Search for videos of a champion
python youtube_measure.py --search "Kai'Sa"

# Or use a direct URL
python youtube_measure.py "https://youtube.com/watch?v=..." --champion "Kai'Sa"
```

### YouTube Workflow

1. **Search**: `python youtube_measure.py --search "Azir"`
2. **Select**: Pick a video from results (3-star showcases work great)
3. **Download**: Video auto-downloads to `downloads/` folder
4. **Measure**: Step through with controls below
5. **Save**: Press `S` to save results

### Finding Good Videos

Search for:
- `"TFT Set 16 [champion] 3 star"` - Best for isolated fights
- `"TFT [champion] carry gameplay"` - Lots of attack sequences
- `"TFT Set 16 [champion] spotlight"` - Often clear footage

Look for:
- 1080p or higher resolution
- Clear view of champion attacking
- Isolated 1v1 fights when possible

## Recording Requirements

For accurate measurements:
- **FPS**: 120+ (240 ideal) - more frames = more precision
- **Resolution**: 1080p minimum
- **Setup**: Isolated 1v1 fight (use Practice Tool or controlled board)
- **Items**: Remove items from test champion for cleaner timing
- **Distance**: Fixed hex distance between attacker and target

## Usage

### Interactive Mode (Recommended)

Step through video frame-by-frame and mark events manually:

```bash
python measure_timing.py gameplay.mp4 --champion Caitlyn --mode interactive
```

**Controls:**
- `SPACE` or `→`: Next frame
- `←`: Previous frame
- `a`: Mark attack start (animation begins)
- `p`: Mark projectile spawn (projectile appears)
- `d`: Mark damage frame (HP bar changes)
- `s`: Mark spell cast
- `q`: Quit and compute results

### Auto Mode

Automatic detection using computer vision (less accurate):

```bash
python measure_timing.py gameplay.mp4 --champion Caitlyn --mode auto
```

### Calibrate Mode

Set detection regions first, then auto-analyze:

```bash
python measure_timing.py gameplay.mp4 --champion Caitlyn --mode calibrate
```

## What to Measure

### Attack Timing
1. **Attack Start**: First frame where attack animation begins
2. **Projectile Spawn**: Frame where projectile becomes visible (ranged)
3. **Damage Frame**: Frame where target HP bar decreases

**Attack Windup** = (Projectile Spawn - Attack Start) frames

### Spell Timing
1. **Cast Start**: First frame of cast animation (mana consumed)
2. **Effect Frame**: When spell effect appears/damage happens

## Output

Results saved to JSON:

```json
{
  "champion": "Caitlyn",
  "video_fps": 120,
  "events": [
    {"frame": 100, "time_ms": 833.3, "type": "attack_start"},
    {"frame": 112, "time_ms": 933.3, "type": "projectile"},
    {"frame": 125, "time_ms": 1041.7, "type": "damage"}
  ],
  "timing": {
    "attack_windup_frames": 12,
    "attack_windup_seconds": 0.1
  }
}
```

## Tips for Accurate Measurement

1. **Multiple Samples**: Measure 5+ attacks and average
2. **Consistent Distance**: Keep same hex distance between units
3. **Watch for Crits**: Crit animations may have different timing
4. **Spell Stars**: Measure at different star levels if timing differs

## Updating timing_constants.json

After measurement, update the main timing file:

```python
import json

# Load measurement
with open('caitlyn_timing.json') as f:
    measured = json.load(f)

# Load constants
with open('../data/timing_constants.json') as f:
    constants = json.load(f)

# Update
constants['TFT16_Caitlyn']['timing']['attack_windup_seconds'] = measured['timing']['attack_windup_seconds']
constants['TFT16_Caitlyn']['timing']['attack_windup_frames'] = measured['timing']['attack_windup_frames']
constants['TFT16_Caitlyn']['timing']['source'] = 'measured'
constants['TFT16_Caitlyn']['timing']['confidence'] = 'high'

# Save
with open('../data/timing_constants.json', 'w') as f:
    json.dump(constants, f, indent=2)
```
