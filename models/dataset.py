"""PyTorch dataset for TFT simulator training rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset

from .feature_engineering import TFTFeatureEngineer

try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional dependency
    pq = None


JSONISH_COLUMNS = {
    "board_names",
    "board_stars",
    "trait_names",
    "trait_counts",
    "augments",
    "units",
    "traits",
    "opponent_units",
    "opponent_traits",
}


def _decode_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in ("[", "{"):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


class TFTDataset(Dataset[Dict[str, torch.Tensor]]):
    """Structured dataset matching ``TFTTransformerV2`` input schema."""

    def __init__(
        self,
        data_dir: str | Path,
        rows: Optional[Sequence[Dict[str, Any]]] = None,
        max_units: int = 14,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        augment_vocab_size: int = 375,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.max_units = max_units
        self.champion_vocab_size = champion_vocab_size
        self.item_vocab_size = item_vocab_size
        self.augment_vocab_size = augment_vocab_size
        self.feature_engineer = TFTFeatureEngineer()
        self.rows = list(rows) if rows is not None else self._load_rows(self.data_dir)
        self.game_ids = [int(row.get("game_id", idx)) for idx, row in enumerate(self.rows)]

        self.champion_to_idx = self._build_champion_lookup()
        self.item_to_idx = self._build_item_lookup()
        self.augment_to_idx = self._build_augment_lookup()
        self.trait_order = [trait.api_name for trait in self.feature_engineer.traits]

    def _load_rows(self, root: Path) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if pq is not None:
            for path in sorted(root.rglob("*.parquet")):
                table = pq.read_table(path)
                for row in table.to_pylist():
                    rows.append(self._normalize_row(row))
        for path in sorted(root.rglob("*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    rows.append(self._normalize_row(json.loads(line)))
        return rows

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(row)
        for key in JSONISH_COLUMNS:
            if key in normalized:
                normalized[key] = _decode_jsonish(normalized[key])
        return normalized

    def _build_champion_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        champions = sorted(self.feature_engineer.champion_costs.keys())
        capacity = self.champion_vocab_size - 2
        for index, champion in enumerate(champions[:capacity], start=2):
            lookup[champion] = index
        return lookup

    def _build_item_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        items = sorted(self.feature_engineer.item_stats.keys())
        capacity = self.item_vocab_size - 2
        for index, item in enumerate(items[:capacity], start=2):
            lookup[item] = index
        return lookup

    def _build_augment_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        augments = sorted(self.feature_engineer.augment_encoding.keys())
        capacity = self.augment_vocab_size - 2
        for index, augment in enumerate(augments[:capacity], start=2):
            lookup[augment] = index
        return lookup

    def __len__(self) -> int:
        return len(self.rows)

    def _encode_units(self, row: Dict[str, Any], prefix: str) -> Tuple[torch.Tensor, ...]:
        units = self.feature_engineer._extract_units(row, prefix=prefix)  # noqa: SLF001
        champion_ids = torch.zeros(self.max_units, dtype=torch.long)
        star_levels = torch.zeros(self.max_units, dtype=torch.long)
        items = torch.zeros((self.max_units, 3), dtype=torch.long)
        positions = torch.zeros(self.max_units, dtype=torch.long)
        costs = torch.zeros(self.max_units, dtype=torch.long)
        mask = torch.zeros(self.max_units, dtype=torch.bool)

        for idx, unit in enumerate(units[: self.max_units]):
            champion = str(unit.get("champion_id", ""))
            champion_ids[idx] = self.champion_to_idx.get(champion, 1)
            star_levels[idx] = max(0, min(3, int(unit.get("star_level", 1))))
            costs[idx] = max(0, min(7, int(self.feature_engineer.champion_costs.get(champion, 0))))
            raw_position = unit.get("position")
            if raw_position is not None:
                position = max(0, min(27, int(raw_position)))
                positions[idx] = position + 1  # 0 reserved for padding/unknown

            for item_slot, raw_item in enumerate((unit.get("items") or [])[:3]):
                canonical_item = self.feature_engineer._canonical_item_name(raw_item)  # noqa: SLF001
                items[idx, item_slot] = self.item_to_idx.get(canonical_item, 1)
            mask[idx] = True

        return champion_ids, star_levels, items, positions, costs, mask

    def _encode_traits(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        traits = self.feature_engineer._extract_traits(row, prefix=prefix)  # noqa: SLF001
        tensor = torch.zeros(len(self.trait_order), dtype=torch.float32)
        for index, trait_name in enumerate(self.trait_order):
            tensor[index] = float(traits.get(trait_name, 0))
        return tensor

    def _encode_augments(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        if prefix == "opponent_":
            raw = _decode_jsonish(row.get("opponent_augments", []))
            if not raw:
                return torch.zeros(3, dtype=torch.long)
            augments = []
            for item in list(raw)[:3]:
                augments.append(str(item))
            while len(augments) < 3:
                augments.append("")
        else:
            augments = self.feature_engineer._extract_augments(row)  # noqa: SLF001

        encoded = [self.augment_to_idx.get(name, 1) if name else 0 for name in augments[:3]]
        while len(encoded) < 3:
            encoded.append(0)
        return torch.tensor(encoded, dtype=torch.long)

    def _encode_game_state(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        level = float(row.get(f"{prefix}level", row.get("level", 1)))
        hp = float(row.get(f"{prefix}hp", row.get("hp", 100)))
        gold = float(row.get(f"{prefix}gold", row.get("gold", 0)))
        streak = row.get(f"{prefix}streak")
        if streak is None:
            win_streak = float(row.get(f"{prefix}win_streak", row.get("win_streak", 0)) or 0)
            loss_streak = float(row.get(f"{prefix}loss_streak", row.get("loss_streak", 0)) or 0)
            streak = win_streak - loss_streak
        streak = float(streak)
        round_num = float(row.get("round", 0))
        stage = float(int(round_num // 7) + 1)
        return torch.tensor(
            [
                max(0.0, min(1.0, level / 10.0)),
                max(0.0, min(1.0, hp / 100.0)),
                max(0.0, min(1.0, gold / 100.0)),
                max(-1.0, min(1.0, streak / 20.0)),
                max(0.0, min(1.0, round_num / 60.0)),
                max(0.0, min(1.0, stage / 10.0)),
            ],
            dtype=torch.float32,
        )

    def _targets(self, row: Dict[str, Any]) -> Dict[str, torch.Tensor]:
        combat_result = row.get("combat_result")
        if combat_result in (0, 1):
            fight_result = float(combat_result)
        else:
            win_streak = int(row.get("win_streak", 0) or 0)
            loss_streak = int(row.get("loss_streak", 0) or 0)
            fight_result = 1.0 if win_streak > 0 and loss_streak == 0 else 0.0

        placement = int(row.get("placement", 8) or 8)
        placement = max(1, min(8, placement)) - 1
        return {
            "fight_result": torch.tensor([fight_result], dtype=torch.float32),
            "damage_dealt": torch.tensor([float(row.get("damage_dealt", row.get("damage", 0.0)) or 0.0)], dtype=torch.float32),
            "placement": torch.tensor([placement], dtype=torch.long),
        }

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        row = self.rows[index]
        sample: Dict[str, torch.Tensor] = {}

        player_fields = self._encode_units(row, prefix="")
        sample["player_champion_ids"] = player_fields[0]
        sample["player_star_levels"] = player_fields[1]
        sample["player_items"] = player_fields[2]
        sample["player_positions"] = player_fields[3]
        sample["player_costs"] = player_fields[4]
        sample["player_mask"] = player_fields[5]
        sample["player_traits"] = self._encode_traits(row, prefix="")
        sample["player_augments"] = self._encode_augments(row, prefix="")
        sample["player_game_state"] = self._encode_game_state(row, prefix="")

        opponent_fields = self._encode_units(row, prefix="opponent_")
        sample["opponent_champion_ids"] = opponent_fields[0]
        sample["opponent_star_levels"] = opponent_fields[1]
        sample["opponent_items"] = opponent_fields[2]
        sample["opponent_positions"] = opponent_fields[3]
        sample["opponent_costs"] = opponent_fields[4]
        sample["opponent_mask"] = opponent_fields[5]
        sample["opponent_traits"] = self._encode_traits(row, prefix="opponent_")
        sample["opponent_augments"] = self._encode_augments(row, prefix="opponent_")
        sample["opponent_game_state"] = self._encode_game_state(row, prefix="opponent_")

        sample.update(self._targets(row))
        return sample
