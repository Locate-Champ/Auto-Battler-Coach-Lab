"""TFT Coach - Main entry point."""

import asyncio
import signal
import sys
import threading
from pathlib import Path

from app.config import config
from app.watcher import LogWatcher, GameEvent
from app.state import StateManager, GameState
from app.server import WebSocketServer


class TFTCoach:
    """Main application class."""

    def __init__(self, with_server: bool = True):
        self.state_manager = StateManager()
        self.watcher = LogWatcher(
            log_dir=config.metatft_log_dir,
            file_patterns=config.log_files,
        )
        self.with_server = with_server
        self.server = WebSocketServer(host=config.host, port=config.port, state_manager=self.state_manager) if with_server else None
        self._running = False

    def _on_game_event(self, event: GameEvent):
        """Handle incoming game events."""
        # Update state
        self.state_manager.process_event(event)

    def _on_state_change(self, state: GameState):
        """Handle state changes."""
        # Broadcast to connected clients
        if self.server:
            self.server.on_state_change(state)

    def start(self):
        """Start the TFT Coach."""
        print("=" * 50)
        print("  TFT Coach - Personal Coaching Overlay")
        print("=" * 50)
        print()

        # Register event handlers
        self.watcher.on_event(self._on_game_event)
        self.state_manager.on_state_change(self._on_state_change)

        # Process existing logs to get current state
        print("[INIT] Processing existing logs...")
        self.watcher.process_existing_logs()

        # Start watching for new events
        print()
        print("[INIT] Starting log watcher...")
        if not self.watcher.start():
            print("[ERROR] Failed to start log watcher")
            print("[HINT] Make sure MetaTFT is installed and has been run at least once")
            return False

        self._running = True
        print()
        print("[READY] TFT Coach is running!")
        print()

        if self.server:
            print(f"[SERVER] Overlay URL: http://{config.host}:{config.port}/overlay")
            print(f"[SERVER] WebSocket:  ws://{config.host}:{config.port}/ws")
            print()

        print("[INFO] Waiting for game events... (Ctrl+C to quit)")
        print()

        return True

    def stop(self):
        """Stop the TFT Coach."""
        print()
        print("[SHUTDOWN] Stopping TFT Coach...")
        self.watcher.stop()
        self._running = False
        print("[SHUTDOWN] Goodbye!")

    def run(self):
        """Run the coach until interrupted."""
        if not self.start():
            return

        # Handle Ctrl+C gracefully
        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Run server if enabled
        if self.server:
            self.server.run()
        else:
            # Keep running without server
            try:
                while self._running:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TFT Coach - Personal Coaching Overlay")
    parser.add_argument("--no-server", action="store_true", help="Run without WebSocket server")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")
    args = parser.parse_args()

    if args.port != 8765:
        config.port = args.port

    coach = TFTCoach(with_server=not args.no_server)
    coach.run()


if __name__ == "__main__":
    main()
