"""Configuration for Auto-Battler Coach."""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""

    # MetaTFT log directory (Windows path)
    metatft_log_dir: Path = Path(
        os.path.expandvars(r"%LOCALAPPDATA%\Overwolf\Log\Apps\MetaTFT")
    )

    # Key log files to watch
    log_files: list[str] = None

    # WebSocket server
    host: str = "127.0.0.1"
    port: int = 8765

    # Data directory
    data_dir: Path = Path(__file__).parent.parent / "data"

    def __post_init__(self):
        if self.log_files is None:
            self.log_files = [
                "background.html.log",
                "win_chance.html.log",
            ]

    @property
    def personal_notes_path(self) -> Path:
        return self.data_dir / "personal_notes.yaml"

    @property
    def rules_path(self) -> Path:
        return self.data_dir / "rules.yaml"

    @property
    def history_db_path(self) -> Path:
        return self.data_dir / "history.db"


# Global config instance
config = Config()
