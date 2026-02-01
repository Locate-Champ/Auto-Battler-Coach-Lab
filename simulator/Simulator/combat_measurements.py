import json
from pathlib import Path


DEFAULT_MEASUREMENTS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "measurements" / "combat_measurements.json"
)


def load_combat_measurements(path=None):
    measurements_path = Path(path) if path else DEFAULT_MEASUREMENTS_PATH
    try:
        with measurements_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {
            "schema_version": None,
            "source": str(measurements_path),
            "measurements": [],
            "by_champion": {},
        }

    measurements = payload.get("measurements", [])
    by_champion = {}
    for entry in measurements:
        champion_id = entry.get("champion_id")
        if champion_id:
            by_champion.setdefault(champion_id, []).append(entry)

    return {
        "schema_version": payload.get("schema_version"),
        "source": str(measurements_path),
        "measurements": measurements,
        "by_champion": by_champion,
    }
