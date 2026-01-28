"""File system watcher for MetaTFT log files."""

import asyncio
import os
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass, field

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .parser import LogParser, GameEvent


@dataclass
class FilePosition:
    """Track read position in a file."""
    path: Path
    position: int = 0
    last_size: int = 0


class LogFileHandler(FileSystemEventHandler):
    """Handles file system events for log files."""

    def __init__(
        self,
        log_dir: Path,
        file_patterns: list[str],
        on_event: Callable[[GameEvent], None],
    ):
        self.log_dir = log_dir
        self.file_patterns = file_patterns
        self.on_event = on_event
        self.parser = LogParser()
        self.file_positions: dict[str, FilePosition] = {}

    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Check if this is a file we care about
        if not self._should_watch(path):
            return

        print(f"[WATCHER] File modified: {path.name}")

        # Process new lines
        self._process_file(path)

    def _should_watch(self, path: Path) -> bool:
        """Check if we should watch this file."""
        name = path.name

        # Check exact matches
        if name in self.file_patterns:
            return True

        # Check pattern matches (e.g., background.html.*.log)
        for pattern in self.file_patterns:
            if pattern.endswith(".log"):
                base = pattern.replace(".log", "")
                if name.startswith(base) and name.endswith(".log"):
                    return True

        return False

    def _process_file(self, path: Path):
        """Read new content from file and parse events."""
        path_str = str(path)

        # Get or create file position tracker
        if path_str not in self.file_positions:
            self.file_positions[path_str] = FilePosition(path=path)

        pos = self.file_positions[path_str]

        try:
            # Check file size
            current_size = path.stat().st_size

            # If file got smaller (rotated), reset position
            if current_size < pos.last_size:
                pos.position = 0

            pos.last_size = current_size

            # Read new content
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                f.seek(pos.position)
                new_lines = f.readlines()
                pos.position = f.tell()

            # Parse and emit events
            if new_lines:
                print(f"[WATCHER] Read {len(new_lines)} new lines from {path.name}")
            for line in new_lines:
                if event := self.parser.parse_line(line):
                    print(f"[WATCHER] Event: {event.event_type.value} - {event.data}")
                    self.on_event(event)

        except (IOError, OSError) as e:
            print(f"Error reading {path}: {e}")


class LogWatcher:
    """Watches MetaTFT log files for game events."""

    def __init__(
        self,
        log_dir: Path,
        file_patterns: Optional[list[str]] = None,
    ):
        self.log_dir = log_dir
        self.file_patterns = file_patterns or [
            "background.html.log",
            "win_chance.html.log",
            "augment_recommendations.html.log",
        ]
        self.observer: Optional[Observer] = None
        self.event_callbacks: list[Callable[[GameEvent], None]] = []
        self._running = False

    def on_event(self, callback: Callable[[GameEvent], None]):
        """Register a callback for game events."""
        self.event_callbacks.append(callback)

    def _emit_event(self, event: GameEvent):
        """Emit event to all registered callbacks."""
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in event callback: {e}")

    def start(self):
        """Start watching log files."""
        if not self.log_dir.exists():
            print(f"Warning: Log directory does not exist: {self.log_dir}")
            print("Make sure MetaTFT is installed and has been run at least once.")
            return False

        handler = LogFileHandler(
            log_dir=self.log_dir,
            file_patterns=self.file_patterns,
            on_event=self._emit_event,
        )

        self.observer = Observer()
        self.observer.schedule(handler, str(self.log_dir), recursive=False)
        self.observer.start()
        self._running = True

        print(f"Started watching: {self.log_dir}")
        print(f"Patterns: {self.file_patterns}")

        return True

    def stop(self):
        """Stop watching log files."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self._running = False
            print("Stopped watching logs")

    @property
    def is_running(self) -> bool:
        return self._running

    def process_existing_logs(self):
        """Process existing log files to get current game state."""
        if not self.log_dir.exists():
            return

        parser = LogParser()
        events = []

        for pattern in self.file_patterns:
            log_path = self.log_dir / pattern
            if log_path.exists():
                try:
                    with open(log_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                        lines = f.readlines()
                        events.extend(parser.parse_lines(lines))
                except (IOError, OSError) as e:
                    print(f"Error reading {log_path}: {e}")

        # Sort by timestamp and emit
        events.sort(key=lambda e: e.timestamp)
        for event in events:
            self._emit_event(event)

        print(f"Processed {len(events)} events from existing logs")
