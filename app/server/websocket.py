"""WebSocket server for real-time overlay updates."""

import asyncio
import json
from typing import Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path

from app.state import GameState


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.active_connections:
            return

        message_json = json.dumps(message)
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


class WebSocketServer:
    """WebSocket server for TFT Coach overlay."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.app = FastAPI(title="TFT Coach")
        self.manager = ConnectionManager()
        self._current_state: Optional[GameState] = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up FastAPI routes."""

        @self.app.get("/")
        async def root():
            """Redirect to overlay."""
            return HTMLResponse(
                content='<html><body><h1>TFT Coach Server</h1>'
                '<p>Open <a href="/overlay">overlay</a></p></body></html>'
            )

        @self.app.get("/overlay")
        async def overlay():
            """Serve the overlay HTML."""
            overlay_path = Path(__file__).parent.parent.parent / "overlay" / "index.html"
            if overlay_path.exists():
                return HTMLResponse(content=overlay_path.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Overlay not found</h1>")

        @self.app.get("/api/state")
        async def get_state():
            """Get current game state."""
            if self._current_state:
                return self._current_state.to_dict()
            return {"error": "No state available"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.manager.connect(websocket)

            # Send current state on connect
            if self._current_state:
                await websocket.send_json(self._current_state.to_dict())

            try:
                while True:
                    # Keep connection alive, handle any client messages
                    data = await websocket.receive_text()
                    # For now, just echo back
                    print(f"[WS] Received: {data}")
            except WebSocketDisconnect:
                self.manager.disconnect(websocket)

    async def broadcast_state(self, state: GameState):
        """Broadcast state update to all clients."""
        self._current_state = state
        await self.manager.broadcast(state.to_dict())

    def on_state_change(self, state: GameState):
        """Callback for state changes (sync wrapper)."""
        self._current_state = state
        # Schedule broadcast in event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.manager.broadcast(state.to_dict()))
        except RuntimeError:
            # No running loop - we'll broadcast on next connection
            pass

    def run(self):
        """Run the server (blocking)."""
        print(f"[SERVER] Starting on http://{self.host}:{self.port}")
        print(f"[SERVER] Overlay: http://{self.host}:{self.port}/overlay")
        print(f"[SERVER] WebSocket: ws://{self.host}:{self.port}/ws")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

    async def run_async(self):
        """Run the server asynchronously."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        await server.serve()
