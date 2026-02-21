"""Set 16.5 unlock requirement tracking and shop gating.

This module implements per-player unlock progression based on the
`data/unlock requirements.csv` table and enforces:
1) Locked units are excluded from normal shop rolls.
2) Most unlocks are granted only after combat checks.
   (Bard, Sylas, and Tahm Kench can unlock during planning/non-combat events.)
3) The next generated shop after unlock guarantees unlocked unit(s).
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .constants import CHAMPIONS_BY_COST, CHAMPION_TRAITS

_DEFAULT_UNLOCK_ORDER: List[str] = [
    "aatrox",
    "aurelionsol",
    "bard",
    "baronnashor",
    "brock",
    "darius",
    "diana",
    "fizz",
    "galio",
    "graves",
    "gwen",
    "kaisa",
    "kalista",
    "kennen",
    "kobuko",
    "leblanc",
    "mel",
    "nasus",
    "nidalee",
    "orianna",
    "poppy",
    "renekton",
    "riftherald",
    "ryze",
    "sett",
    "singed",
    "skarner",
    "sylas",
    "thex",
    "tahmkench",
    "thresh",
    "tryndamere",
    "veigar",
    "volibear",
    "warwick",
    "xerath",
    "yone",
    "yorick",
    "zaahen",
    "ziggs",
]

_DEFAULT_LEVEL_REQUIREMENTS: Dict[str, Optional[int]] = {
    "aatrox": 8,
    "aurelionsol": None,
    "bard": None,
    "baronnashor": 10,
    "brock": None,
    "darius": None,
    "diana": 6,
    "fizz": 7,
    "galio": None,
    "graves": None,
    "gwen": None,
    "kaisa": 7,
    "kalista": None,
    "kennen": None,
    "kobuko": 7,
    "leblanc": None,
    "mel": None,
    "nasus": None,
    "nidalee": None,
    "orianna": None,
    "poppy": None,
    "renekton": None,
    "riftherald": None,
    "ryze": 9,
    "sett": 8,
    "singed": None,
    "skarner": 7,
    "sylas": 9,
    "thex": None,
    "tahmkench": None,
    "thresh": None,
    "tryndamere": None,
    "veigar": 7,
    "volibear": 8,
    "warwick": 7,
    "xerath": None,
    "yone": None,
    "yorick": None,
    "zaahen": None,
    "ziggs": 9,
}

_CSV_UNIT_ALIASES = {
    "aatrox": "aatrox",
    "aurelion sol": "aurelionsol",
    "bard": "bard",
    "baron nashor": "baronnashor",
    "brock": "brock",
    "darius": "darius",
    "diana": "diana",
    "fizz": "fizz",
    "galio": "galio",
    "graves": "graves",
    "gwen": "gwen",
    "kai'sa": "kaisa",
    "kalista": "kalista",
    "kennen": "kennen",
    "kobuko & yuumi": "kobuko",
    "leblanc": "leblanc",
    "mel": "mel",
    "nasus": "nasus",
    "nidalee": "nidalee",
    "orianna": "orianna",
    "poppy": "poppy",
    "renekton": "renekton",
    "rift herald": "riftherald",
    "ryze": "ryze",
    "sett": "sett",
    "singed": "singed",
    "skarner": "skarner",
    "sylas": "sylas",
    "t-hex": "thex",
    "tahm kench": "tahmkench",
    "thresh": "thresh",
    "tryndamere": "tryndamere",
    "veigar": "veigar",
    "volibear": "volibear",
    "warwick": "warwick",
    "xerath": "xerath",
    "yone": "yone",
    "yorick": "yorick",
    "zaahen": "zaahen",
    "ziggs": "ziggs",
}

_RADABONS_ITEM = "rabadonsdeathcap"
_GARGOYLE_ITEM = "gargoylestoneplate"
_FIRST_CAROUSEL_ROUND = 3
_TRIALS_OF_TWILIGHT_AUGMENTS = frozenset({
    "TFT16_Augment_XinZhaoCarry",
    "TFT16_Augment_XinZhaoCarryII",
})
_REGION_TRAITS = frozenset({
    "bilgewater",
    "demacia",
    "freljord",
    "ionia",
    "ixtal",
    "noxus",
    "piltover",
    "shadow_isles",
    "shurima",
    "targon",
    "void",
    "yordle",
    "zaun",
})
_TANK_TRAITS = frozenset({"defender", "bruiser", "warden", "juggernaut", "vanguard"})
_SHURIMA_UNLOCK_UNITS = frozenset({"nasus", "renekton", "xerath"})
_SHURIMA_THRESHOLDS = {
    "nasus": (2, 3, 4),
    "renekton": (2, 3, 4),
    "xerath": (3, 4, 5),
}
_NON_COMBAT_UNLOCK_UNITS = frozenset({"bard", "sylas", "tahmkench"})

# Quest reward ladders from LittleBuddyBot Ixtal quest sheet.
# Rewards are Sunshards granted at each completion milestone.
_DEFAULT_IXTAL_QUEST_REWARD_LADDERS: Dict[str, Tuple[int, ...]] = {
    "qiyana takedown": (30, 50, 80, 80, 80),
    "2 star neeko": (40, 30, 30, 30, 30),
    "3 star qiyana": (150, 150, 200, 200, 200),
    "buy xp easy": (40, 40, 40, 40, 40),
    "buy xp med": (50, 50, 50, 50, 50),
    "champs died": (105, 125, 175, 225, 250),
    "champs killed": (70, 90, 110, 140, 150),
    "clear item bench": (80, 80, 100, 120, 120),
    "clear mind": (100, 100, 125, 150, 150),
    "cluttered mind": (100, 100, 125, 150, 150),
    "damage dealt": (20, 30, 40, 40, 40),
    "damage blocked": (20, 20, 20, 30, 30),
    "earn interest": (70, 90, 120, 160, 200),
    "neeko survive": (20, 30, 40, 50, 50),
    "shop reroll small": (40, 40, 30, 30, 30),
    "shop reroll med": (90, 90, 50, 50, 50),
    "shop reroll hard": (135, 135, 70, 70, 70),
    "total armor": (20, 30, 40, 50, 50),
    "total mr": (20, 30, 40, 50, 50),
    "total gold": (60, 75, 90, 140, 180),
    "win streak short": (100, 125, 150, 175, 200),
    "2 star milio": (50, 40, 40, 40),
    "2 star skarner": (100, 40, 40, 40),
    "lose 2": (175, 200),
    "ixtal trait": (500,),
    "lose big streak": (500,),
    "big health loss": (300, 300),
    "mix streak short": (200, 280, 400, 500, 700),
    "lose": (150, 225, 300, 400),
    "lose hard": (275, 400, 500, 700),
    "lose small streak": (120, 200, 200, 300, 300),
    "buy xp hard": (125, 125, 100, 100, 100),
    "1 hp": (700, 700, 700, 700, 700),
    "level up": (400,),
    "low health": (300, 300, 300, 300),
    "1 unit alive": (500, 500, 500, 500),
    "zero gold": (90, 90, 90, 90),
    "brock survive": (300, 300, 300),
    "win late": (1000,),
}

_IXTAL_QUEST_NAME_ALIASES: Dict[str, str] = {
    "buy xp": "buy xp easy",
    "buy xp medium": "buy xp med",
    "shop reroll": "shop reroll small",
    "shop reroll medium": "shop reroll med",
    "kill": "champs killed",
    "low streak short": "mix streak short",
    "low streak": "mix streak short",
    "explorer 3 trait": "ixtal trait",
    "2 star": "2 star neeko",
    "3 star": "3 star qiyana",
}


def _normalize_item_name(item_name: str) -> str:
    value = item_name.strip().lower()
    for prefix in ("tft_item_", "artifact_"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return re.sub(r"[^a-z0-9]+", "", value)


def _normalize_csv_unit_name(unit_name: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", unit_name.strip().lower())
    return _CSV_UNIT_ALIASES.get(normalized)


def _normalize_ixtal_quest_name(quest_name: str) -> str:
    value = quest_name.strip()
    if not value:
        return ""

    value = value.replace("TFT16_Explorer_", "")
    value = value.replace("XP", "Xp")
    value = re.sub(r"Quest$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = value.replace("_", " ")
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    value = re.sub(r"\s+", " ", value)
    return _IXTAL_QUEST_NAME_ALIASES.get(value, value)


@dataclass(frozen=True)
class PreCombatUnitSnapshot:
    """Snapshot of a player's on-board unit state at combat start."""

    instance_id: str
    name: str
    api_name: str
    row: int
    star_level: int
    item_count: int
    normalized_items: Tuple[str, ...]
    traits: Tuple[str, ...]
    max_hp: float
    omnivamp: float
    is_tank: bool


@dataclass
class CombatUnlockContext:
    """Post-combat facts used to evaluate unlock requirements."""

    phase: str  # "pvp" or "pve"
    outcome: Optional[str] = None  # "win" | "loss" | "draw" | None
    shadow_souls_gained: int = 0
    draven_gold_dropped: int = 0
    dead_instance_ids: Set[str] = field(default_factory=set)
    victim_api_names: Set[str] = field(default_factory=set)
    has_trials_of_twilight: bool = False


@dataclass
class UnlockProgress:
    """Per-player unlock progression state."""

    unlocked_units: Set[str] = field(default_factory=set)
    allowed_shop_units: Set[str] = field(default_factory=set)
    pending_shop_guarantees: List[str] = field(default_factory=list)

    rerolls_before_first_carousel: int = 0
    sold_two_star_names: Set[str] = field(default_factory=set)

    unique_targonians: Set[str] = field(default_factory=set)
    unique_void_units: Set[str] = field(default_factory=set)
    unique_yordle_or_bilgewater_units: Set[str] = field(default_factory=set)
    unique_demacia_star_levels: Set[Tuple[str, int]] = field(default_factory=set)
    unique_ionia_yordle_defender_star_levels: Set[Tuple[str, int]] = field(default_factory=set)
    unique_yordle_bruiser_invoker_star_levels: Set[Tuple[str, int]] = field(default_factory=set)
    unique_piltover_star_levels: Set[Tuple[str, int]] = field(default_factory=set)
    unique_zaun_or_juggernaut_units: Set[str] = field(default_factory=set)

    total_shadow_souls: int = 0
    total_bilgewater_serpents_gained: int = 0
    total_bilgewater_serpents_spent: int = 0
    total_ixtal_sunshards: int = 0
    total_player_hp_lost: int = 0
    total_draven_gold_dropped: int = 0
    ixtal_quest_completion_counts: Dict[str, int] = field(default_factory=dict)

    void_active_player_combats: int = 0
    xinzhao_3star_combats: int = 0

    shurima_win_streak_with_azir: int = 0
    shurima_loss_streak_with_azir: int = 0
    shurima_alt_streak_with_azir: int = 0
    shurima_last_result_with_azir: Optional[str] = None


class UnlockRequirementsManager:
    """Tracks unlock requirements and exposes per-player shop constraints."""

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        ixtal_quests_csv_path: Optional[Path] = None,
    ):
        self._all_pool_units = {
            name
            for champs_by_cost in CHAMPIONS_BY_COST.values()
            for name in champs_by_cost.keys()
        }
        order, level_reqs = self._load_requirements_from_csv(csv_path)
        if not order:
            order = list(_DEFAULT_UNLOCK_ORDER)
        self.unlock_order: List[str] = [
            unit_name for unit_name in order if unit_name in self._all_pool_units
        ]
        self.level_requirements: Dict[str, Optional[int]] = {
            unit_name: level_reqs.get(unit_name, _DEFAULT_LEVEL_REQUIREMENTS.get(unit_name))
            for unit_name in self.unlock_order
        }
        self.unlock_units: Set[str] = set(self.unlock_order)
        self.base_shop_units: Set[str] = self._all_pool_units - self.unlock_units
        self.ixtal_quest_reward_ladders: Dict[str, Tuple[int, ...]] = (
            self._load_ixtal_quest_reward_ladders(ixtal_quests_csv_path)
        )

    def initialize_player(self, player: Any) -> None:
        progress = self._progress(player)
        progress.allowed_shop_units = set(self.base_shop_units)
        progress.pending_shop_guarantees.clear()

    def allowed_shop_units_for_player(self, player: Any) -> Set[str]:
        return set(self._progress(player).allowed_shop_units)

    def consume_shop_guarantees_for_player(self, player: Any) -> List[str]:
        progress = self._progress(player)
        guaranteed = list(progress.pending_shop_guarantees)
        progress.pending_shop_guarantees.clear()
        return guaranteed

    def build_precombat_snapshot(self, player: Any, combat_team: Iterable[Any]) -> List[PreCombatUnitSnapshot]:
        team_by_instance: Dict[str, Any] = {}
        for unit in combat_team:
            instance_id = getattr(unit, "instance_id", "")
            if instance_id:
                team_by_instance[instance_id] = unit

        snapshots: List[PreCombatUnitSnapshot] = []
        for (row, _col), champ in player.board.items():
            traits = tuple(CHAMPION_TRAITS.get(champ.name, []))
            normalized_items = tuple(_normalize_item_name(item) for item in champ.items)
            team_unit = team_by_instance.get(champ.instance_id)

            max_hp = 0.0
            omnivamp = 0.0
            is_tank = any(trait in _TANK_TRAITS for trait in traits)
            if team_unit is not None:
                stats = getattr(team_unit, "stats", None)
                if stats is not None:
                    max_hp = float(getattr(stats, "max_hp", 0.0) or 0.0)
                    omnivamp = float(getattr(stats, "omnivamp", 0.0) or 0.0)
                is_tank = bool(getattr(team_unit, "is_frontline", is_tank))

            snapshots.append(
                PreCombatUnitSnapshot(
                    instance_id=champ.instance_id,
                    name=champ.name,
                    api_name=champ.api_name,
                    row=row,
                    star_level=champ.star_level,
                    item_count=len(champ.items),
                    normalized_items=normalized_items,
                    traits=traits,
                    max_hp=max_hp,
                    omnivamp=omnivamp,
                    is_tank=is_tank,
                )
            )
        return snapshots

    def evaluate_post_combat(
        self,
        *,
        player: Any,
        precombat_units: List[PreCombatUnitSnapshot],
        context: CombatUnlockContext,
    ) -> List[str]:
        progress = self._progress(player)
        self._update_progress(player=player, precombat_units=precombat_units, context=context)

        newly_unlocked = self._evaluate_unlocks(
            player=player,
            progress=progress,
            precombat_units=precombat_units,
            context=context,
        )
        if newly_unlocked:
            self._apply_new_unlocks(progress, newly_unlocked)

        return newly_unlocked

    def evaluate_noncombat_unlocks(self, player: Any) -> List[str]:
        """Evaluate unlocks that are allowed to trigger outside combat."""
        progress = self._progress(player)
        newly_unlocked = self._evaluate_unlocks(
            player=player,
            progress=progress,
            precombat_units=[],
            context=CombatUnlockContext(phase="pve", outcome=None),
            candidate_units=_NON_COMBAT_UNLOCK_UNITS,
        )
        if newly_unlocked:
            self._apply_new_unlocks(progress, newly_unlocked)
        return newly_unlocked

    def record_reroll(self, player: Any, round_num: int) -> None:
        if round_num < _FIRST_CAROUSEL_ROUND:
            self._progress(player).rerolls_before_first_carousel += 1
        self.evaluate_noncombat_unlocks(player)

    def record_sell(self, player: Any, champ_name: str, star_level: int) -> None:
        if star_level < 2:
            return
        if champ_name in {"jarvaniv", "garen"}:
            self._progress(player).sold_two_star_names.add(champ_name)
        self.evaluate_noncombat_unlocks(player)

    def record_player_hp_lost(self, player: Any, amount: int) -> None:
        if amount > 0:
            self._progress(player).total_player_hp_lost += int(amount)

    def record_bilgewater_serpents_gained(self, player: Any, amount: int) -> None:
        if amount > 0:
            self._progress(player).total_bilgewater_serpents_gained += int(amount)

    def record_bilgewater_serpents_spent(self, player: Any, amount: int) -> None:
        if amount > 0:
            self._progress(player).total_bilgewater_serpents_spent += int(amount)
        self.evaluate_noncombat_unlocks(player)

    def record_ixtal_sunshards_gained(self, player: Any, amount: int) -> None:
        if amount > 0:
            self._progress(player).total_ixtal_sunshards += int(amount)

    def record_ixtal_quest_completion(
        self,
        player: Any,
        quest_name: str,
        reward_override: Optional[int] = None,
    ) -> int:
        progress = self._progress(player)
        normalized_name = _normalize_ixtal_quest_name(quest_name)
        rewards = self.ixtal_quest_reward_ladders.get(normalized_name, ())
        reward = int(reward_override or 0)

        if reward <= 0 and rewards:
            completion_idx = progress.ixtal_quest_completion_counts.get(normalized_name, 0)
            reward = int(rewards[min(completion_idx, len(rewards) - 1)])

        if reward <= 0:
            return 0

        progress.total_ixtal_sunshards += reward
        if normalized_name:
            progress.ixtal_quest_completion_counts[normalized_name] = (
                progress.ixtal_quest_completion_counts.get(normalized_name, 0) + 1
            )
        return reward

    def _progress(self, player: Any) -> UnlockProgress:
        progress = getattr(player, "unlock_progress", None)
        if progress is None:
            progress = UnlockProgress()
            player.unlock_progress = progress
        return progress

    def _load_requirements_from_csv(
        self,
        csv_path: Optional[Path],
    ) -> Tuple[List[str], Dict[str, Optional[int]]]:
        if csv_path is None:
            csv_path = Path(__file__).resolve().parents[2] / "data" / "unlock requirements.csv"
        if not csv_path.exists():
            return [], {}

        order: List[str] = []
        level_reqs: Dict[str, Optional[int]] = {}
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as handle:
                raw_lines = handle.read().splitlines()

            header_idx = -1
            for idx, line in enumerate(raw_lines):
                if line.strip().lower().startswith("unit,"):
                    header_idx = idx
                    break
            if header_idx < 0:
                return [], {}

            reader = csv.DictReader(io.StringIO("\n".join(raw_lines[header_idx:])))
            for row in reader:
                raw_unit = (row.get("Unit") or "").strip()
                if not raw_unit:
                    continue
                unit_name = _normalize_csv_unit_name(raw_unit)
                if unit_name is None:
                    continue
                order.append(unit_name)
                raw_level = (row.get("Level Req") or "").strip()
                digits = re.findall(r"\d+", raw_level)
                level_reqs[unit_name] = int(digits[0]) if digits else None
        except Exception:
            return [], {}
        return order, level_reqs

    def _load_ixtal_quest_reward_ladders(
        self,
        csv_path: Optional[Path],
    ) -> Dict[str, Tuple[int, ...]]:
        artifact_path = Path(__file__).resolve().with_name("ixtal_quest_rewards.json")
        artifact_ladders = self._load_ixtal_quest_reward_artifact(artifact_path)
        if artifact_ladders:
            return artifact_ladders

        data_dir = Path(__file__).resolve().parents[2] / "data"
        candidate_paths: List[Path] = []
        if csv_path is not None:
            candidate_paths.append(csv_path)
        else:
            candidate_paths.extend(
                [
                    data_dir / "ixtal quests.csv",
                    data_dir / "ixtal_quests.csv",
                    data_dir / "ixtal quests list.csv",
                ]
            )

        for path in candidate_paths:
            ladders = self._parse_ixtal_quest_rewards_csv(path)
            if ladders:
                return ladders

        return dict(_DEFAULT_IXTAL_QUEST_REWARD_LADDERS)

    @staticmethod
    def _load_ixtal_quest_reward_artifact(path: Path) -> Dict[str, Tuple[int, ...]]:
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        ladders: Dict[str, Tuple[int, ...]] = {}
        for raw_name, raw_rewards in payload.items():
            name = _normalize_ixtal_quest_name(str(raw_name))
            if not name:
                continue

            if not isinstance(raw_rewards, (list, tuple)):
                continue
            rewards: List[int] = []
            for reward in raw_rewards:
                if isinstance(reward, (int, float)):
                    reward_value = int(reward)
                elif isinstance(reward, str):
                    digits = re.findall(r"\d+", reward)
                    reward_value = int(digits[0]) if digits else 0
                else:
                    reward_value = 0

                if reward_value > 0:
                    rewards.append(reward_value)

            if rewards:
                ladders[name] = tuple(rewards)
        return ladders

    @staticmethod
    def _parse_ixtal_quest_rewards_csv(csv_path: Path) -> Dict[str, Tuple[int, ...]]:
        if not csv_path.exists():
            return {}

        ladders: Dict[str, Tuple[int, ...]] = {}
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as handle:
                raw_lines = handle.read().splitlines()

            header_idx = -1
            for idx, line in enumerate(raw_lines):
                normalized = line.strip().lower()
                if normalized.startswith("icon,name,") or normalized.startswith("name,"):
                    header_idx = idx
                    break

            if header_idx < 0:
                return {}

            reader = csv.DictReader(io.StringIO("\n".join(raw_lines[header_idx:])))
            for row in reader:
                raw_name = (row.get("Name") or row.get("name") or "").strip()
                quest_name = _normalize_ixtal_quest_name(raw_name)
                if not quest_name:
                    continue

                rewards: List[int] = []
                for column in ("Prize 2", "Prize 3", "Prize 4", "Prize 5", "Prize 6"):
                    raw_reward = (row.get(column) or "").strip()
                    if not raw_reward:
                        continue
                    digits = re.findall(r"\d+", raw_reward)
                    if digits:
                        rewards.append(int(digits[0]))

                if rewards:
                    ladders[quest_name] = tuple(rewards)
        except Exception:
            return {}

        return ladders

    def _update_progress(
        self,
        *,
        player: Any,
        precombat_units: List[PreCombatUnitSnapshot],
        context: CombatUnlockContext,
    ) -> None:
        progress = self._progress(player)

        for unit in precombat_units:
            traits = set(unit.traits)
            if "targon" in traits:
                progress.unique_targonians.add(unit.name)
            if "void" in traits:
                progress.unique_void_units.add(unit.name)
            if "yordle" in traits or "bilgewater" in traits:
                progress.unique_yordle_or_bilgewater_units.add(unit.name)
            if "demacia" in traits:
                progress.unique_demacia_star_levels.add((unit.name, unit.star_level))
            if traits.intersection({"ionia", "yordle", "defender"}):
                progress.unique_ionia_yordle_defender_star_levels.add((unit.name, unit.star_level))
            if traits.intersection({"yordle", "bruiser", "invoker"}):
                progress.unique_yordle_bruiser_invoker_star_levels.add((unit.name, unit.star_level))
            if "piltover" in traits:
                progress.unique_piltover_star_levels.add((unit.name, unit.star_level))
            if traits.intersection({"zaun", "juggernaut"}):
                progress.unique_zaun_or_juggernaut_units.add(unit.name)

        if context.shadow_souls_gained > 0:
            progress.total_shadow_souls += int(context.shadow_souls_gained)
        if context.draven_gold_dropped > 0:
            progress.total_draven_gold_dropped += int(context.draven_gold_dropped)

        has_azir = any(unit.name == "azir" for unit in precombat_units)
        if has_azir and context.outcome in {"win", "loss"}:
            if context.outcome == "win":
                progress.shurima_win_streak_with_azir += 1
                progress.shurima_loss_streak_with_azir = 0
            else:
                progress.shurima_loss_streak_with_azir += 1
                progress.shurima_win_streak_with_azir = 0

            if progress.shurima_last_result_with_azir is None:
                progress.shurima_alt_streak_with_azir = 1
            elif progress.shurima_last_result_with_azir != context.outcome:
                progress.shurima_alt_streak_with_azir += 1
            else:
                progress.shurima_alt_streak_with_azir = 1
            progress.shurima_last_result_with_azir = context.outcome
        else:
            progress.shurima_win_streak_with_azir = 0
            progress.shurima_loss_streak_with_azir = 0
            progress.shurima_alt_streak_with_azir = 0
            progress.shurima_last_result_with_azir = None

        if context.phase == "pvp" and self._void_is_active(precombat_units):
            progress.void_active_player_combats += 1

        if context.has_trials_of_twilight and any(
            unit.name == "xinzhao" and unit.star_level >= 3
            for unit in precombat_units
        ):
            progress.xinzhao_3star_combats += 1

    def _evaluate_unlocks(
        self,
        *,
        player: Any,
        progress: UnlockProgress,
        precombat_units: List[PreCombatUnitSnapshot],
        context: CombatUnlockContext,
        candidate_units: Optional[Set[str]] = None,
    ) -> List[str]:
        newly_unlocked: List[str] = []
        shurima_unlock_count = self._count_shurima_unlocks(progress)
        for unit_name in self.unlock_order:
            if candidate_units is not None and unit_name not in candidate_units:
                continue
            if unit_name in progress.unlocked_units:
                continue
            level_req = self.level_requirements.get(unit_name)
            if level_req is not None and player.level < level_req:
                continue
            if self._is_requirement_met(
                unit_name=unit_name,
                player=player,
                progress=progress,
                precombat_units=precombat_units,
                context=context,
                shurima_unlock_count=shurima_unlock_count,
            ):
                newly_unlocked.append(unit_name)
        return newly_unlocked

    def _apply_new_unlocks(self, progress: UnlockProgress, newly_unlocked: List[str]) -> None:
        progress.unlocked_units.update(newly_unlocked)
        progress.allowed_shop_units.update(newly_unlocked)
        self._queue_shop_guarantees(progress, newly_unlocked)

    @staticmethod
    def _queue_shop_guarantees(progress: UnlockProgress, guaranteed_units: Iterable[str]) -> None:
        queued = set(progress.pending_shop_guarantees)
        for unit_name in guaranteed_units:
            if unit_name in queued:
                continue
            progress.pending_shop_guarantees.append(unit_name)
            queued.add(unit_name)

    def _is_requirement_met(
        self,
        *,
        unit_name: str,
        player: Any,
        progress: UnlockProgress,
        precombat_units: List[PreCombatUnitSnapshot],
        context: CombatUnlockContext,
        shurima_unlock_count: int,
    ) -> bool:
        if unit_name == "aatrox":
            return any(unit.omnivamp >= 0.40 for unit in precombat_units)
        if unit_name == "aurelionsol":
            return len(progress.unique_targonians) >= 5
        if unit_name == "bard":
            return progress.rerolls_before_first_carousel >= 4
        if unit_name == "baronnashor":
            return len(progress.unique_void_units) >= 7
        if unit_name == "brock":
            return progress.total_ixtal_sunshards >= 500
        if unit_name == "darius":
            return progress.total_draven_gold_dropped >= 1
        if unit_name == "diana":
            return self._has_named_unit_with_items(precombat_units, "leona", min_star=2, min_items=3)
        if unit_name == "fizz":
            return len(progress.unique_yordle_or_bilgewater_units) >= 5
        if unit_name == "galio":
            return len(progress.unique_demacia_star_levels) >= 12
        if unit_name == "graves":
            return self._has_named_unit_with_items(precombat_units, "twistedfate", min_items=2)
        if unit_name == "gwen":
            return progress.total_shadow_souls >= 20
        if unit_name == "kaisa":
            return self._has_trait_unit_with_items(precombat_units, "longshot", min_items=3)
        if unit_name == "kalista":
            return progress.total_shadow_souls >= 70
        if unit_name == "kennen":
            return len(progress.unique_ionia_yordle_defender_star_levels) >= 7
        if unit_name == "kobuko":
            return len(progress.unique_yordle_bruiser_invoker_star_levels) >= 6
        if unit_name == "leblanc":
            return self._has_named_unit_with_items(precombat_units, "sion", min_items=2)
        if unit_name == "mel":
            return self._ambessa_death_requirement_met(precombat_units, context)
        if unit_name == "nasus":
            threshold = _SHURIMA_THRESHOLDS["nasus"][min(shurima_unlock_count, 2)]
            return progress.shurima_loss_streak_with_azir >= threshold
        if unit_name == "nidalee":
            return self._count_all_copies(player, "neeko", min_star=2) >= 2
        if unit_name == "orianna":
            return self._has_trait_unit_with_items(precombat_units, "piltover", min_items=2)
        if unit_name == "poppy":
            return self._has_trait_combo_unit_with_items(precombat_units, {"demacia", "yordle"}, min_items=2)
        if unit_name == "renekton":
            threshold = _SHURIMA_THRESHOLDS["renekton"][min(shurima_unlock_count, 2)]
            return progress.shurima_win_streak_with_azir >= threshold
        if unit_name == "riftherald":
            return progress.void_active_player_combats >= 8
        if unit_name == "ryze":
            return self._count_region_traits(precombat_units) >= 4
        if unit_name == "sett":
            # Board row 0 is closest to the enemy, so front rows are 0 and 1.
            return sum(1 for unit in precombat_units if unit.row < 2) == 1
        if unit_name == "singed":
            return (
                len(progress.unique_zaun_or_juggernaut_units) >= 4
                and progress.total_player_hp_lost >= 35
            )
        if unit_name == "skarner":
            return any(
                (not unit.is_tank) and (_GARGOYLE_ITEM in unit.normalized_items)
                for unit in precombat_units
            )
        if unit_name == "sylas":
            return {"jarvaniv", "garen"}.issubset(progress.sold_two_star_names)
        if unit_name == "thex":
            return len(progress.unique_piltover_star_levels) >= 9
        if unit_name == "tahmkench":
            return progress.total_bilgewater_serpents_spent >= 450
        if unit_name == "thresh":
            return progress.total_shadow_souls >= 175
        if unit_name == "tryndamere":
            return self._has_named_unit_with_items(precombat_units, "ashe", min_items=1)
        if unit_name == "veigar":
            return any(
                sum(1 for item in unit.normalized_items if item == _RADABONS_ITEM) >= 2
                for unit in precombat_units
            )
        if unit_name == "volibear":
            return any(unit.max_hp >= 3800.0 for unit in precombat_units)
        if unit_name == "warwick":
            return (
                self._has_named_unit_with_items(precombat_units, "jinx", min_items=1)
                and self._has_named_unit_with_items(precombat_units, "vi", min_items=1)
            )
        if unit_name == "xerath":
            threshold = _SHURIMA_THRESHOLDS["xerath"][min(shurima_unlock_count, 2)]
            return progress.shurima_alt_streak_with_azir >= threshold
        if unit_name == "yone":
            return self._count_all_copies(player, "yasuo", min_star=3) >= 1
        if unit_name == "yorick":
            return self._has_named_unit_with_items(precombat_units, "viego", min_star=2, min_items=1)
        if unit_name == "zaahen":
            return (
                context.has_trials_of_twilight
                and progress.xinzhao_3star_combats >= 5
            )
        if unit_name == "ziggs":
            return self._has_trait_combo_unit_with_items(precombat_units, {"yordle", "zaun"}, min_items=3)
        return False

    def _ambessa_death_requirement_met(
        self,
        precombat_units: List[PreCombatUnitSnapshot],
        context: CombatUnlockContext,
    ) -> bool:
        candidates = [
            unit
            for unit in precombat_units
            if unit.name == "ambessa" and unit.star_level >= 2 and unit.item_count >= 1
        ]
        if not candidates:
            return False
        if any(unit.instance_id in context.dead_instance_ids for unit in candidates):
            return True
        # Rust fallback: victim API names do not include instance/star/item details.
        return "TFT16_Ambessa" in context.victim_api_names

    @staticmethod
    def _count_all_copies(player: Any, unit_name: str, min_star: int) -> int:
        count = 0
        for champ in player.board.values():
            if champ.name == unit_name and champ.star_level >= min_star:
                count += 1
        for champ in player.bench:
            if champ is not None and champ.name == unit_name and champ.star_level >= min_star:
                count += 1
        return count

    @staticmethod
    def _count_region_traits(precombat_units: List[PreCombatUnitSnapshot]) -> int:
        active_regions: Set[str] = set()
        for unit in precombat_units:
            for trait in unit.traits:
                if trait in _REGION_TRAITS:
                    active_regions.add(trait)
        return len(active_regions)

    @staticmethod
    def _has_named_unit_with_items(
        precombat_units: List[PreCombatUnitSnapshot],
        unit_name: str,
        *,
        min_star: int = 1,
        min_items: int = 1,
    ) -> bool:
        return any(
            unit.name == unit_name and unit.star_level >= min_star and unit.item_count >= min_items
            for unit in precombat_units
        )

    @staticmethod
    def _has_trait_unit_with_items(
        precombat_units: List[PreCombatUnitSnapshot],
        trait_name: str,
        *,
        min_items: int,
    ) -> bool:
        return any(
            trait_name in unit.traits and unit.item_count >= min_items
            for unit in precombat_units
        )

    @staticmethod
    def _has_trait_combo_unit_with_items(
        precombat_units: List[PreCombatUnitSnapshot],
        traits: Set[str],
        *,
        min_items: int,
    ) -> bool:
        return any(
            bool(set(unit.traits).intersection(traits)) and unit.item_count >= min_items
            for unit in precombat_units
        )

    @staticmethod
    def _void_is_active(precombat_units: List[PreCombatUnitSnapshot]) -> bool:
        void_count = sum(1 for unit in precombat_units if "void" in unit.traits)
        return void_count >= 2

    @staticmethod
    def _count_shurima_unlocks(progress: UnlockProgress) -> int:
        return sum(1 for unit in progress.unlocked_units if unit in _SHURIMA_UNLOCK_UNITS)
