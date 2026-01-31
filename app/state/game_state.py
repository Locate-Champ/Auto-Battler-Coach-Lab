"""Game state data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class GamePhase(Enum):
    """Current phase of the game."""
    NOT_IN_GAME = "not_in_game"
    LOADING = "loading"
    CAROUSEL = "carousel"
    PVE = "pve"
    PVP = "pvp"
    AUGMENT = "augment"
    ITEM_SELECT = "item_select"


@dataclass
class Unit:
    """A champion unit on board or bench."""
    character_id: str  # e.g., "TFT16_Ekko"
    star_level: int = 1
    items: list[str] = field(default_factory=list)
    position: Optional[tuple[int, int]] = None  # (row, col)

    @property
    def name(self) -> str:
        """Extract clean name from character_id."""
        # TFT16_Ekko -> Ekko
        if "_" in self.character_id:
            return self.character_id.split("_")[-1]
        return self.character_id


@dataclass
class PlayerState:
    """State of a player (self or opponent)."""
    name: str
    health: int = 100
    level: int = 1
    is_self: bool = False
    board_units: list[Unit] = field(default_factory=list)
    traits: dict[str, int] = field(default_factory=dict)  # trait -> count


@dataclass
class GameState:
    """Complete game state reconstructed from log events."""

    # Game info
    game_id: Optional[str] = None
    game_phase: GamePhase = GamePhase.NOT_IN_GAME
    stage: str = "0-0"
    game_start_time: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)

    # Player state
    player: PlayerState = field(default_factory=lambda: PlayerState(name="", is_self=True))
    xp: str = "0/0"
    gold: int = 0
    win_streak: int = 0
    loss_streak: int = 0

    # Augments
    augments: list[str] = field(default_factory=list)
    augment_options: list[str] = field(default_factory=list)
    augment_armory_active: bool = False

    # Bench
    bench_units: list[Unit] = field(default_factory=list)

    # Opponents
    opponents: dict[str, PlayerState] = field(default_factory=dict)

    # All opponent boards for pool tracking (board_id -> list of units)
    opponent_boards: dict[str, list[Unit]] = field(default_factory=dict)

    # Scouting
    currently_scouting: Optional[str] = None

    # Predictions
    win_chance: Optional[int] = None
    evaluation_checkpoints: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "game_id": self.game_id,
            "game_phase": self.game_phase.value,
            "stage": self.stage,
            "game_start_time": self.game_start_time.isoformat() if self.game_start_time else None,
            "last_update": self.last_update.isoformat(),
            "player": {
                "name": self.player.name,
                "health": self.player.health,
                "level": self.player.level,
            },
            "xp": self.xp,
            "gold": self.gold,
            "win_streak": self.win_streak,
            "loss_streak": self.loss_streak,
            "augments": self.augments,
            "augment_options": self.augment_options,
            "augment_armory_active": self.augment_armory_active,
            "opponents": {
                name: {"name": p.name, "health": p.health, "level": p.level}
                for name, p in self.opponents.items()
            },
            "currently_scouting": self.currently_scouting,
            "win_chance": self.win_chance,
            "evaluation_checkpoints": self.evaluation_checkpoints,
            # Board units with positions
            "board_units": [
                {
                    "id": f"cell_{u.position[0] * 7 + u.position[1]}" if u.position else None,
                    "character_id": u.character_id,
                    "name": u.name,
                    "stars": u.star_level,
                    "items": u.items,
                    "position": {"row": u.position[0], "col": u.position[1]} if u.position else None,
                }
                for u in self.player.board_units
            ],
            # Bench units
            "bench_units": [
                {
                    "character_id": u.character_id,
                    "name": u.name,
                    "stars": u.star_level,
                    "items": u.items,
                }
                for u in self.bench_units
            ],
            # Opponent boards for pool tracking
            "opponent_boards": {
                board_id: [
                    {
                        "character_id": u.character_id,
                        "name": u.name,
                        "stars": u.star_level,
                    }
                    for u in units
                ]
                for board_id, units in self.opponent_boards.items()
            },
        }

    @property
    def stage_number(self) -> int:
        """Get stage as number (e.g., '2-3' -> 2)."""
        try:
            return int(self.stage.split("-")[0])
        except (ValueError, IndexError):
            return 0

    @property
    def round_number(self) -> int:
        """Get round as number (e.g., '2-3' -> 3)."""
        try:
            return int(self.stage.split("-")[1])
        except (ValueError, IndexError):
            return 0

    @property
    def is_in_game(self) -> bool:
        """Check if currently in a game."""
        return self.game_phase != GamePhase.NOT_IN_GAME

    def reset(self):
        """Reset state for a new game."""
        self.game_id = None
        self.game_phase = GamePhase.NOT_IN_GAME
        self.stage = "0-0"
        self.game_start_time = None
        self.player = PlayerState(name="", is_self=True)
        self.xp = "0/0"
        self.gold = 0
        self.win_streak = 0
        self.loss_streak = 0
        self.augments = []
        self.augment_options = []
        self.augment_armory_active = False
        self.bench_units = []
        self.opponents = {}
        self.opponent_boards = {}
        self.currently_scouting = None
        self.win_chance = None
        self.evaluation_checkpoints = []
