"""Load and normalize TFT game data for combat simulation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "game_data"


@dataclass(frozen=True)
class CanonicalId:
    api_name: str
    name: str


def load_game_data(data_dir: Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Load champions, items, and traits from jsonl sources.

    Returns:
        dict: {"champions": {...}, "items": {...}, "traits": {...}}
    """

    resolved_dir = data_dir or DATA_DIR
    champions = _load_champions(resolved_dir / "champions.jsonl")
    items = _load_items(resolved_dir / "items.jsonl")
    traits = _load_traits(
        resolved_dir / "traits.jsonl",
        resolved_dir / "trait_effects.jsonl",
        resolved_dir / "trait_id_map.json",
    )

    return {"champions": champions, "items": items, "traits": traits}


def _load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _normalize_api_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value)


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def _parse_json_field(raw: Any) -> Any:
    if raw is None:
        return {}
    if isinstance(raw, float) and math.isnan(raw):
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    raw_text = str(raw)
    if not raw_text:
        return {}
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text


def _champion_stats_by_star(base_stats: Mapping[str, Any]) -> Dict[str, Dict[str, float]]:
    stat_keys = [
        "stat_armor",
        "stat_attackSpeed",
        "stat_critChance",
        "stat_critMultiplier",
        "stat_damage",
        "stat_hp",
        "stat_initialMana",
        "stat_magicResist",
        "stat_mana",
        "stat_range",
    ]
    base = {key: float(base_stats.get(key, 0.0) or 0.0) for key in stat_keys}
    return {
        "1": base,
        "2": base.copy(),
        "3": base.copy(),
    }


def _load_champions(path: Path) -> Dict[str, Any]:
    champions: Dict[str, Any] = {}
    for row in _load_jsonl(path):
        api_name = _normalize_api_name(row.get("apiName"))
        name = _normalize_text(row.get("name"))
        if not api_name or not name:
            continue
        traits_pipe = row.get("traits_pipe")
        traits = [trait.strip() for trait in str(traits_pipe).split("|") if trait.strip()] if traits_pipe else []

        champion = {
            "id": CanonicalId(api_name=api_name, name=name),
            "name": name,
            "apiName": api_name,
            "aliases": {"name": name},
            "cost": row.get("cost"),
            "role": row.get("role"),
            "traits": traits,
            "ability": {
                "name": _normalize_text(row.get("ability_name")),
                "desc": _normalize_text(row.get("ability_desc")),
                "icon": _normalize_text(row.get("ability_icon")),
            },
            "icons": {
                "icon": _normalize_text(row.get("icon")),
                "square": _normalize_text(row.get("squareIcon")),
                "tile": _normalize_text(row.get("tileIcon")),
            },
            "stats_by_star": _champion_stats_by_star(row),
        }
        champions[api_name] = champion
    return champions


def _load_items(path: Path) -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for row in _load_jsonl(path):
        api_name = _normalize_api_name(row.get("apiName"))
        name = _normalize_text(row.get("name"))
        if not api_name or not name:
            continue
        item = {
            "id": CanonicalId(api_name=api_name, name=name),
            "name": name,
            "apiName": api_name,
            "aliases": {"name": name},
            "desc": _normalize_text(row.get("desc")),
            "icon": _normalize_text(row.get("icon")),
            "unique": bool(row.get("unique", False)),
            "effects": _parse_json_field(row.get("effects_json")),
            "tags": _parse_json_field(row.get("tags_json")),
            "associatedTraits": _parse_json_field(row.get("associatedTraits_json")),
            "incompatibleTraits": _parse_json_field(row.get("incompatibleTraits_json")),
            "composition": _parse_json_field(row.get("composition_json")),
        }
        items[api_name] = item
    return items


def _load_traits(
    traits_path: Path,
    effects_path: Path,
    trait_id_map_path: Path,
) -> Dict[str, Any]:
    traits: Dict[str, Any] = {}
    for row in _load_jsonl(traits_path):
        api_name = _normalize_api_name(row.get("apiName"))
        name = _normalize_text(row.get("name"))
        if not api_name or not name:
            continue
        traits[api_name] = {
            "id": CanonicalId(api_name=api_name, name=name),
            "name": name,
            "apiName": api_name,
            "desc": _normalize_text(row.get("desc")),
            "icon": _normalize_text(row.get("icon")),
            "breakpoints": [],
        }

    effects_by_trait = _load_trait_effects(effects_path)
    name_map = _load_trait_name_map(trait_id_map_path)

    for api_name, trait in traits.items():
        trait["breakpoints"] = effects_by_trait.get(api_name, [])
        trait["aliases"] = name_map.get(api_name, {})

    return traits


def _load_trait_effects(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    effects: Dict[str, List[Dict[str, Any]]] = {}
    for row in _load_jsonl(path):
        api_name = _normalize_api_name(row.get("trait_apiName"))
        if not api_name:
            continue
        effects.setdefault(api_name, []).append(
            {
                "minUnits": row.get("minUnits"),
                "maxUnits": row.get("maxUnits"),
                "style": row.get("style"),
                "variables": _parse_json_field(row.get("variables_json")),
            }
        )
    return effects


def _load_trait_name_map(path: Path) -> Dict[str, Dict[str, str | None]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping: Dict[str, Dict[str, str | None]] = {}
    for api_name, payload in raw.items():
        if isinstance(payload, dict):
            display_name = payload.get("displayName")
            icon = payload.get("icon")
        else:
            display_name = payload
            icon = None
        mapping[str(api_name)] = {
            "displayName": str(display_name) if display_name is not None else None,
            "icon": str(icon) if icon is not None else None,
        }

    return _expand_trait_aliases(mapping)


def _expand_trait_aliases(
    mapping: Dict[str, Dict[str, str | None]],
) -> Dict[str, Dict[str, str | None]]:
    expanded: Dict[str, Dict[str, str | None]] = {}
    for api_stub, meta in mapping.items():
        expanded[api_stub] = meta
        expanded[f"TFT16_{api_stub}"] = meta
        expanded[f"TFT_{api_stub}"] = meta
    return expanded
