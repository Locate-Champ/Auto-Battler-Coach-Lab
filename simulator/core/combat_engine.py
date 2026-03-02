"""
TFT Combat Simulator Engine v2

Core combat simulation for TFT Set 16 with:
- Physical/Magic damage with armor/MR reduction
- Critical strikes (25% base chance, 140% multiplier)
- Star level scaling (1.8x HP, 1.5x AD for 2-star)
- Attack speed and mana generation
- Ability casting with targeting
- Hex-based movement and pathfinding
- Item effects system
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._augment_manager import (  # noqa: F401
    _AUGMENTS_DATA,
    _AUGMENTS_LOADED,
    AugmentManager,
)
from ._combat_actions import _CombatActionsMixin  # noqa: F401
from ._combat_processing import _CombatProcessingMixin  # noqa: F401
from ._combat_runners import _CombatRunnersMixin  # noqa: F401
from ._combat_types import (  # noqa: F401
    _COMBAT_DATA_CACHE,
    Ability,
    AbilityType,
    Buff,
    CombatStats,
    DamageType,
    DotEffect,
    Item,
    TargetingType,
    Unit,
    UnitState,
    _load_combat_data,
    _star_val,
)
from ._hex_grid import HexGrid  # noqa: F401
from ._item_database import (  # noqa: F401
    _ITEM_EFFECTS_LOADED,
    _ITEMS_LOADED,
    AbilityDatabase,
    ItemDatabase,
)
from ._trait_manager import TeamTraitState, TraitManager  # noqa: F401

# Import champion ability handlers
try:
    from .champion_abilities import ChampionAbilities

    _ABILITIES_LOADED = True
except ImportError:
    _ABILITIES_LOADED = False
    ChampionAbilities = None


# =============================================================================
# COMBAT ENGINE
# =============================================================================


class CombatEngine(_CombatRunnersMixin, _CombatProcessingMixin, _CombatActionsMixin):
    """
    TFT Combat Simulation Engine v2.

    Features:
    - Full combat simulation with abilities
    - Hex-based movement and pathfinding
    - Item effects system
    - Buff/debuff tracking
    """

    # Game constants
    HEX_SIZE = 180  # Game units per hex
    # Mana per attack by role (Set 15+ role rework)
    MANA_PER_ATTACK_BY_ROLE = {
        "ADCarry": 10,
        "APCaster": 7,
        "APTank": 5,
        "ADTank": 5,
        "Tank": 5,
        "Defender": 5,
        "ADFighter": 10,
        "Specialist": 10,
        "Support": 7,
        "Assassin": 10,
    }
    MANA_PER_ATTACK_DEFAULT = 10
    MANA_ON_DAMAGE_TAKEN_CAP = 42.5  # Max mana per damage instance
    ATTACK_SPEED_CAP = 5.0  # Hard cap on attack speed
    MOVE_SPEED_BASE = 550  # Base movement speed
    HEX_MOVE_TIME = 0.5  # Seconds to move one hex at base speed

    # Star scaling
    HP_SCALING = {1: 1.0, 2: 1.8, 3: 3.24}
    AD_SCALING = {1: 1.0, 2: 1.5, 3: 2.25}

    def __init__(self, combat_data_path: Optional[Path] = None, logging_enabled: bool = True):
        """Initialize the combat engine with game data."""
        if combat_data_path is None:
            combat_data_path = Path(__file__).parent.parent / "data" / "combat_data.json"

        self.combat_data = _load_combat_data(combat_data_path)
        self.logging_enabled = logging_enabled

        self.champions = self.combat_data.get("champions", {})
        self.constants = self.combat_data.get("constants", {})

        # Combat state
        self.time = 0.0
        self.tick_rate = 0.033  # ~30 FPS simulation
        self.combat_log: List[Dict] = []
        self.units: List[Unit] = []
        self.projectiles: List[Dict] = []
        self._alive_team0: List[Unit] = []
        self._alive_team1: List[Unit] = []
        self._alive_dirty = False
        self._has_noxus = False
        self._ionic_spark_units: List[Unit] = []  # Units with Ionic Spark (cached)
        self._debug_takedowns: List[Dict[str, Any]] = []
        self._occupied_hexes: set = set()  # Cached occupied hex positions
        self._occupied_dirty = True  # True when occupied cache needs rebuild

        # Trait manager for Blacksmith, Bilgewater, Piltover
        self.trait_manager = TraitManager()
        self._round_persistent_players: Dict[
            int, Any
        ] = {}  # combat team (0/1) -> game-layer Player (or None)

        # Augment manager for augment effects
        self.augment_manager = AugmentManager()

        # Champion ability handlers
        if _ABILITIES_LOADED and ChampionAbilities:
            self.champion_abilities = ChampionAbilities(self)
        else:
            self.champion_abilities = None

    def create_unit(
        self,
        api_name: str,
        star_level: int,
        position: Tuple[int, int],
        team: int,
        items: List[str] = None,
        instance_id: str = "",
    ) -> Optional[Unit]:
        """Create a unit from champion data."""
        champ_data = self.champions.get(api_name)
        if not champ_data:
            print(f"Warning: Champion {api_name} not found in data")
            return None

        base_stats_data = champ_data.get("stats", {})
        timing = champ_data.get("timing", {})

        # Apply star scaling
        hp_mult = self.HP_SCALING.get(star_level, 1.0)
        ad_mult = self.AD_SCALING.get(star_level, 1.0)

        base_stats = CombatStats(
            hp=(base_stats_data.get("hp") or 500) * hp_mult,
            max_hp=(base_stats_data.get("hp") or 500) * hp_mult,
            ad=(base_stats_data.get("ad") or 50) * ad_mult,
            ap=0.0,
            attack_speed=base_stats_data.get("attackSpeed") or 0.7,
            armor=base_stats_data.get("armor") or 20,
            magic_resist=base_stats_data.get("magicResist") or 20,
            range=int(base_stats_data.get("range") or 1),
            mana=base_stats_data.get("startMana") or 0,
            max_mana=base_stats_data.get("mana") or 100,
            crit_chance=base_stats_data.get("critChance") or 0.25,
            crit_multiplier=base_stats_data.get("critMultiplier") or 1.4,
        )

        # Create ability
        ability = AbilityDatabase.create_ability(api_name, champ_data, star_level)

        # Create unit with copied stats (so items can modify)
        current_stats = base_stats.copy()

        unit = Unit(
            name=champ_data.get("name", api_name).strip(),
            api_name=api_name,
            instance_id=instance_id,
            star_level=star_level,
            stats=current_stats,
            base_stats=base_stats,
            position=position,
            team=team,
            traits=champ_data.get("traits", []),
            ability=ability,
            role=champ_data.get("role", ""),
            attack_windup=timing.get("attackWindup", 0.3),
            missile_speed=timing.get("missileSpeed"),
        )

        # Apply items
        if items:
            for item_name in items:
                item = ItemDatabase.create_item(item_name)
                if item:
                    self.apply_item(unit, item)

        return unit

    def set_round_persistent_players(
        self, team0_player: Any = None, team1_player: Any = None
    ) -> None:
        """Attach per-round persistent game-layer state for combat triggers.

        This is used for effects like Bilgewater takedown currency, which should
        be scoped to the owning player (not the combat engine instance).
        """
        self._round_persistent_players = {0: team0_player, 1: team1_player}

    def apply_item(self, unit: Unit, item: Item):
        """Apply item stats to a unit.

        Note: In Set 16, AD on items is a percentage (e.g., 0.35 = 35% bonus AD).
        Other stats like HP, armor, AP are flat values.
        Emblems also grant their associated trait to the unit.
        """
        unit.items.append(item)

        # Update cached item flags for hot-path checks
        if item.name == "JeweledGauntlet":
            unit._has_jeweled_gauntlet = True
        elif item.name in ("GiantSlayer", "RadiantGiantSlayer"):
            unit._has_giant_slayer = True
        elif item.name == "IonicSpark" or item.name.endswith("IonicSpark"):
            unit._has_ionic_spark = True

        # Check if item is an emblem and grant the trait
        try:
            from simulator.data.set16_items import EMBLEM_TO_TRAIT

            trait = EMBLEM_TO_TRAIT.get(item.name)
            if trait and trait not in unit.traits:
                unit.traits.append(trait)
        except ImportError:
            pass

        for stat, value in item.stats.items():
            if hasattr(unit.stats, stat):
                current = getattr(unit.stats, stat)

                # AD is a percentage multiplier in Set 16 items
                if stat == "ad":
                    # Convert percentage to flat AD based on base AD
                    flat_ad = unit.base_stats.ad * value
                    setattr(unit.stats, stat, current + flat_ad)

                # Flat stats
                elif stat == "hp":
                    # Set 16 item `hp` is flat max HP. Mirror Rust semantics.
                    unit.stats.max_hp += value
                    unit.stats.hp += value
                elif stat == "max_hp":
                    unit.stats.max_hp += value
                    unit.stats.hp += value
                elif stat in ["armor", "magic_resist", "ap"]:
                    setattr(unit.stats, stat, current + value)

                # Percentage stats (already stored as decimals)
                elif stat in [
                    "attack_speed",
                    "crit_chance",
                    "damage_amp",
                    "omnivamp",
                    "crit_multiplier",
                ]:
                    setattr(unit.stats, stat, current + value)

                # Mana stats
                elif stat == "mana_regen":
                    unit.stats.mana_regen += value

                # Bonus HP percentage (Warmog's, Dragon's Claw, Bramble Vest, Sunfire Cape)
                elif stat == "bonus_hp_pct":
                    bonus_hp = unit.base_stats.max_hp * value
                    unit.stats.max_hp += bonus_hp
                    unit.stats.hp += bonus_hp

                else:
                    setattr(unit.stats, stat, current + value)

    def _spawn_azir_soldiers(
        self, team: List[Unit], team_id: int, positions: List[Tuple[int, int]] = None
    ):
        """Spawn Sand Soldiers for Azir.

        In the game loop, soldiers are placed by the player at chosen positions
        (via Player.build_combat_team). This method is a fallback for direct
        combat engine usage (e.g., simulate_1v1) - it places soldiers in
        adjacent free hexes if no positions are specified.

        Soldiers are targetable blockers: enemies will attack them, but
        they don't attack back (0 AD). They have 750 HP, 50 armor/MR.
        Friendly units walk around them.

        Args:
            team: The team to add soldiers to
            team_id: Which team (0 or 1)
            positions: Explicit positions to place soldiers. If None,
                       auto-places adjacent to Azir (fallback).
        """
        for unit in team:
            if unit.api_name != "TFT16_Azir" or not unit.is_alive:
                continue

            if positions:
                # Use player-specified positions
                spots = [(r, c) for r, c in positions if 0 <= r < 4 and 0 <= c < 7]
            else:
                # Fallback: adjacent to Azir
                occupied = self.get_occupied_hexes()
                adjacent = HexGrid.get_neighbors(unit.position)
                spots = [
                    pos
                    for pos in adjacent
                    if pos not in occupied and 0 <= pos[0] < 4 and 0 <= pos[1] < 7
                ]

            for pos in spots[:2]:
                soldier = self.create_unit("TFT16_AzirSoldier", unit.star_level, pos, team_id)
                if soldier:
                    soldier._is_summon = True
                    soldier._summoner = unit.name
                    team.append(soldier)
                    self.units.append(soldier)
                    self._invalidate_occupied_cache()

    def get_occupied_hexes(self) -> set:
        """Get set of all occupied hex positions (cached, rebuilt on death/move)."""
        if self._occupied_dirty:
            self._occupied_hexes = {u.position for u in self.units if u.is_alive}
            self._occupied_dirty = False
        return self._occupied_hexes

    def _invalidate_occupied_cache(self):
        """Mark the occupied hex cache as needing rebuild."""
        self._occupied_dirty = True

    def set_unit_position(self, unit: Unit, new_pos: Tuple[int, int]) -> None:
        """Set a unit's position and invalidate occupied-hex caching.

        Any mid-combat position changes (dash/teleport/forced move) must go
        through this helper so occupied-hex caching stays correct.
        """
        if unit.position == new_pos:
            return
        unit.position = new_pos
        self._invalidate_occupied_cache()

    def log_event(self, event_type: str, **kwargs):
        """Log a combat event."""
        if not self.logging_enabled:
            return
        self.combat_log.append({"time": round(self.time, 2), "type": event_type, **kwargs})

    # -- Runner methods (tick, run_combat, simulate_1v1, etc.) provided by _CombatRunnersMixin --
    # -- Processing methods (find_target, process_attack, cast_ability, etc.) provided by _CombatProcessingMixin --
    # -- Action methods (calculate_damage, apply_damage, heal_unit, etc.) provided by _CombatActionsMixin --


# =============================================================================
# DEMO
# =============================================================================


def main():
    """Demo the combat engine."""
    engine = CombatEngine()

    print("=" * 60)
    print("TFT Combat Simulator v2")
    print("=" * 60)
    print(f"\nLoaded {len(engine.champions)} champions")
    print(f"Available items: {len(ItemDatabase.ITEMS)}")

    # Debug: Show some champion stats including roles
    print("\n--- Champion Debug Info ---")
    for name in ["TFT16_Kaisa", "TFT16_Draven", "TFT16_Jinx", "TFT16_Renekton"]:
        unit = engine.create_unit(name, 2, (0, 0), 0)
        if unit:
            role_type = "Frontline" if unit.is_frontline else "Backline"
            print(
                f"{unit.name} ({unit.role}, {role_type}): HP={unit.stats.hp:.0f}, AD={unit.stats.ad:.0f}, "
                f"AS={unit.stats.attack_speed:.2f}, Range={unit.stats.range}, Mana={unit.stats.mana}/{unit.stats.max_mana}"
            )

    # 1v1: Same cost comparison
    print("\n" + "-" * 60)
    print("1v1: Draven (2*) vs Tristana (2*) - Both 3-cost ADCs")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Tristana", star1=2, star2=2, num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")
    print("Average Abilities Cast:")
    for champ, casts in result["avg_abilities_cast"].items():
        print(f"  {champ}: {casts}")

    # 1v1: Tank vs Tank
    print("\n" + "-" * 60)
    print("1v1: Renekton (2*) vs Leona (2*) - Frontline clash")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Renekton", "TFT16_Leona", star1=2, star2=2, num_simulations=500
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print(f"Average Combat Time: {result['avg_combat_time']}s")

    # 1v1 with items
    print("\n" + "-" * 60)
    print("1v1: Jinx (2*) + IE/LW vs Renekton (2*) + Warmogs/Bramble")
    print("-" * 60)

    result = engine.simulate_1v1(
        "TFT16_Jinx",
        "TFT16_Renekton",
        star1=2,
        star2=2,
        items1=["InfinityEdge", "LastWhisper"],
        items2=["WarmogsArmor", "BrambleVest"],
        num_simulations=500,
    )

    print(f"Simulations: {result['simulations']}")
    for champ, rate in result["win_rate"].items():
        print(f"  {champ}: {rate}% win rate")
    print("Average Damage:")
    for champ, dmg in result["avg_damage"].items():
        print(f"  {champ}: {dmg}")

    # Team fight
    print("\n" + "-" * 60)
    print("Team Fight: 3v3")
    print("-" * 60)

    team0 = [
        engine.create_unit("TFT16_Jinx", 2, (0, 2), 0, ["InfinityEdge"]),
        engine.create_unit("TFT16_Lux", 2, (0, 3), 0, ["RabadonsDeathcap"]),
        engine.create_unit("TFT16_Leona", 2, (1, 3), 0, ["WarmogsArmor"]),
    ]

    team1 = [
        engine.create_unit("TFT16_Draven", 2, (3, 2), 1, ["Bloodthirster"]),
        engine.create_unit("TFT16_Ahri", 2, (3, 3), 1, ["SpearOfShojin"]),
        engine.create_unit("TFT16_Braum", 2, (2, 3), 1, ["GargoyleStoneplate"]),
    ]

    result = engine.run_combat(team0, team1)

    print(f"Winner: Team {result['winner']}")
    print(f"Combat Time: {result['combat_time']}s")
    print(f"Team 0 Survivors: {result['team0_survivors']}")
    print(f"Team 1 Survivors: {result['team1_survivors']}")
    print(f"Team 0 Total Damage: {result['team0_total_damage']}")
    print(f"Team 1 Total Damage: {result['team1_total_damage']}")

    # Show item impact
    print("\n" + "-" * 60)
    print("Item Impact Test: Draven with vs without IE")
    print("-" * 60)

    result_no_items = engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Leona", star1=2, star2=2, num_simulations=300
    )

    result_with_ie = engine.simulate_1v1(
        "TFT16_Draven",
        "TFT16_Leona",
        star1=2,
        star2=2,
        items1=["InfinityEdge"],
        num_simulations=300,
    )

    print(f"No items: Draven {result_no_items['win_rate']['TFT16_Draven']}% win")
    print(f"With IE:  Draven {result_with_ie['win_rate']['TFT16_Draven']}% win")

    # Test Jinx form swap (minigun -> rockets after 18 attacks)
    print("\n" + "-" * 60)
    print("Jinx Form Swap Test: Long fight to see rocket transition")
    print("-" * 60)

    # Jinx vs high HP tank - should see rocket form activate
    result = engine.simulate_1v1(
        "TFT16_Jinx",
        "TFT16_Renekton",
        star1=2,
        star2=2,
        items1=["RedBuff"],  # AS boost helps reach rocket form
        items2=["WarmogsArmor", "DragonsClaw"],  # Very tanky
        num_simulations=100,
    )

    print(f"Jinx win rate: {result['win_rate']['TFT16_Jinx']}%")
    print(f"Average combat time: {result['avg_combat_time']}s (longer = more rockets)")
    print(f"Jinx avg damage: {result['avg_damage']['TFT16_Jinx']}")

    # Tank targeting test
    print("\n" + "-" * 60)
    print("Tank Targeting Test: Frontline should draw aggro")
    print("-" * 60)

    # Setup: Draven (backline) behind Braum (frontline) vs enemy
    team_with_tank = [
        engine.create_unit("TFT16_Braum", 2, (1, 3), 0, ["WarmogsArmor"]),  # Frontline tank
        engine.create_unit("TFT16_Draven", 2, (0, 3), 0, ["InfinityEdge"]),  # Backline carry
    ]
    team_enemy = [
        engine.create_unit("TFT16_Draven", 2, (3, 3), 1, ["InfinityEdge"]),
    ]

    result = engine.run_combat(team_with_tank, team_enemy, verbose=True)

    # Check if Braum took damage (meaning he drew aggro)
    braum = team_with_tank[0]
    draven_friendly = team_with_tank[1]

    print(f"Braum damage taken: {braum.total_damage_taken:.0f}")
    print(f"Draven (friendly) damage taken: {draven_friendly.total_damage_taken:.0f}")
    if braum.total_damage_taken > draven_friendly.total_damage_taken:
        print("SUCCESS: Tank drew aggro as expected!")
    else:
        print("NOTE: Carry took more damage (may be positioning dependent)")

    print("\n" + "=" * 60)
    print("Combat Simulator Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
