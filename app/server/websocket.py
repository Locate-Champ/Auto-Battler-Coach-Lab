"""WebSocket server for real-time overlay updates."""

import asyncio
import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.redux_bridge.handler import ReduxBridgeHandler
from app.state import GameState as AppGameState
from app.state import StateManager
from coach.actions import DecisionType as CoachDecisionType
from coach.coach import Coach
from coach.explain import validate_coach_payload
from coach.scoring.features import champion_cost as coach_champion_cost
from coach.state import GameState as CoachGameState
from coach.state import OpponentState as CoachOpponentState
from coach.state import PlayerState as CoachPlayerState
from coach.state import ShopUnit as CoachShopUnit
from coach.state import UnitState as CoachUnitState
from coach.state import validate_coach_state
from coach.weights import CoachConfig, weights_for_stage


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self.active_connections.add(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            self.active_connections.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        with self._lock:
            connections = list(self.active_connections)

        if not connections:
            return

        print(f"[WS] Broadcasting to {len(self.active_connections)} client(s)")
        message_json = json.dumps(message)
        disconnected = set()

        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


class WebSocketServer:
    """WebSocket server for the Auto-Battler Coach overlay."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        state_manager: Optional[StateManager] = None,
    ):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Auto-Battler Coach")
        self.manager = ConnectionManager()
        self._current_state: Optional[AppGameState] = None
        self._current_payload: Optional[dict] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._state_manager = state_manager
        self._redux_handler = ReduxBridgeHandler()

        trace_dir = Path(__file__).parent.parent.parent / "outputs" / "coach" / "traces"
        self._coach = Coach(trace_dir=trace_dir)
        self._coach_min_interval_sec = 0.75
        self._last_coach_compute_mono = 0.0
        self._last_coach_stage: Optional[str] = None
        self._last_coach_payload: Optional[dict] = None

        self._setup_routes()

    def _should_compute_coach(self, state: AppGameState) -> bool:
        if not state.is_in_game:
            return False
        if not state.player.board_units:
            return False

        now = time.monotonic()
        if state.stage != self._last_coach_stage:
            return True
        return (now - self._last_coach_compute_mono) >= self._coach_min_interval_sec

    def _to_coach_units(
        self,
        *,
        board_units: list,
        bench_units: list,
        prefix: str,
    ) -> tuple[CoachUnitState, ...]:
        out: list[CoachUnitState] = []

        for idx, u in enumerate(board_units):
            pos = u.position if getattr(u, "position", None) is not None else None
            if pos is not None:
                instance_id = f"{prefix}_board_{pos[0]}_{pos[1]}"
            else:
                instance_id = f"{prefix}_board_{idx}"
            out.append(
                CoachUnitState(
                    instance_id=instance_id,
                    champion_id=str(u.character_id),
                    star_level=int(u.star_level),
                    items=tuple(u.items),
                    position=pos,
                    location="board",
                )
            )

        for idx, u in enumerate(bench_units):
            out.append(
                CoachUnitState(
                    instance_id=f"{prefix}_bench_{idx}",
                    champion_id=str(u.character_id),
                    star_level=int(u.star_level),
                    items=tuple(u.items),
                    position=None,
                    location="bench",
                )
            )

        return tuple(out)

    def _to_coach_state(self, state: AppGameState) -> CoachGameState:
        player_xp = None
        try:
            player_xp = int(str(state.xp).split("/", 1)[0])
        except Exception:
            player_xp = None

        player = CoachPlayerState(
            level=int(state.player.level),
            hp=int(state.player.health),
            gold=int(state.gold),
            xp=player_xp,
            win_streak=int(state.win_streak),
            loss_streak=int(state.loss_streak),
        )

        board_and_bench = self._to_coach_units(
            board_units=state.player.board_units,
            bench_units=state.bench_units,
            prefix="self",
        )
        board = tuple(u for u in board_and_bench if u.location == "board")
        bench = tuple(u for u in board_and_bench if u.location == "bench")

        opponents: list[CoachOpponentState] = []
        for opp_id, units in state.opponent_boards.items():
            opp_units = self._to_coach_units(
                board_units=units, bench_units=[], prefix=f"opp_{opp_id}"
            )
            opp_board = tuple(u for u in opp_units if u.location == "board")
            opp_meta = state.opponents.get(opp_id)
            opponents.append(
                CoachOpponentState(
                    opponent_id=str(opp_id),
                    board=opp_board,
                    level=int(opp_meta.level) if opp_meta is not None else None,
                    hp=int(opp_meta.health) if opp_meta is not None else None,
                )
            )

        shop: list[CoachShopUnit] = []
        for u in getattr(state, "shop_units", []) or []:
            cid = getattr(u, "character_id", None)
            if not isinstance(cid, str) or not cid:
                continue
            cost = getattr(u, "cost", None)
            if cost is None:
                cost = coach_champion_cost(cid)
            shop.append(CoachShopUnit(champion_id=cid, cost=int(cost)))

        return CoachGameState(
            stage=str(state.stage),
            player=player,
            board=board,
            bench=bench,
            shop=tuple(shop),
            items=tuple(state.unassigned_items),
            augments=tuple(state.augments),
            opponents=tuple(opponents),
            notes=(f"phase:{state.game_phase.value}",) if state.game_phase else (),
        )

    def _coach_config_for_state(self, state: AppGameState) -> CoachConfig:
        return CoachConfig(
            weights=weights_for_stage(stage_number=state.stage_number),
            combat_base_seed=1337,
            max_candidates_items=20,
            max_candidates_position=20,
            max_candidates_econ=12,
            max_candidates_shop=12,
            top_k=3,
            sim_budget_pass1=24,
            sim_budget_pass2=0,
            sim_budget_pass3=0,
            topk_refine=0,
            max_total_sims=512,
        )

    def _compute_coach_payload(self, state: AppGameState, *, write_trace: bool) -> dict:
        cfg = self._coach_config_for_state(state)
        coach_state = self._to_coach_state(state)
        validation_errors = validate_coach_state(coach_state)
        if validation_errors:
            print(f"[COACH] validate_coach_state: {len(validation_errors)} error(s)")
            for e in validation_errors[:10]:
                print(f"[COACH]  - {e}")

        decisions = (
            CoachDecisionType.ITEMS,
            CoachDecisionType.POSITION,
            CoachDecisionType.ECON,
            CoachDecisionType.SHOP,
        )

        recs_by_decision: dict[str, list[dict]] = {}
        errors_by_decision: dict[str, str] = {}
        for decision in decisions:
            try:
                recs = self._coach.recommend(
                    coach_state, decision, config=cfg, write_trace=write_trace
                )
                recs_by_decision[decision.value] = [
                    {
                        "action": asdict(r.action),
                        "score": asdict(r.score),
                        "explanation": asdict(r.explanation),
                    }
                    for r in recs
                ]
            except Exception as e:
                errors_by_decision[decision.value] = str(e)
                recs_by_decision[decision.value] = []

        payload = {
            "coach_payload_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "coach_state_schema_version": int(getattr(coach_state, "schema_version", 0) or 0),
            "coach_state_validation_errors": validation_errors or None,
            "config": {
                "sim_budget_pass1": cfg.sim_budget_pass1,
                "sim_budget_pass2": cfg.sim_budget_pass2,
                "sim_budget_pass3": cfg.sim_budget_pass3,
                "max_candidates_items": cfg.max_candidates_items,
                "max_candidates_position": cfg.max_candidates_position,
                "max_candidates_econ": cfg.max_candidates_econ,
                "max_candidates_shop": cfg.max_candidates_shop,
                "top_k": cfg.top_k,
            },
            "recommendations": recs_by_decision,
        }
        if errors_by_decision:
            payload["errors"] = errors_by_decision

        payload_errors = validate_coach_payload(payload)
        if payload_errors:
            print(f"[COACH] validate_coach_payload: {len(payload_errors)} error(s)")
            for e in payload_errors[:10]:
                print(f"[COACH]  - {e}")

        return payload

    def _setup_routes(self):
        """Set up FastAPI routes."""

        @self.app.on_event("startup")
        async def startup_event():
            """Capture the event loop on startup for cross-thread broadcasts."""
            self._event_loop = asyncio.get_running_loop()
            print("[WS] Event loop captured for cross-thread broadcasts")

        @self.app.get("/")
        async def root():
            """Redirect to overlay."""
            return HTMLResponse(
                content="<html><body><h1>Auto-Battler Coach Server</h1>"
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
            if self._current_payload:
                return self._current_payload
            if self._current_state:
                return self._current_state.to_dict()
            return {"error": "No state available"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.manager.connect(websocket)

            # Send current state on connect
            if self._current_payload:
                await websocket.send_json(self._current_payload)
            elif self._current_state:
                await websocket.send_json(self._current_state.to_dict())

            try:
                while True:
                    # Keep connection alive, handle any client messages
                    data = await websocket.receive_text()
                    # For now, just echo back
                    print(f"[WS] Received: {data}")
            except WebSocketDisconnect:
                self.manager.disconnect(websocket)

        @self.app.websocket("/network-log")
        async def network_log_endpoint(websocket: WebSocket):
            """WebSocket endpoint for DevTools network command logs."""
            await websocket.accept()
            log_dir = Path(__file__).parent.parent.parent / "outputs" / "network_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"metatft_devtools_network_{timestamp}.jsonl"
            print(f"[WS] Network log connected. Writing to {log_path}")

            try:
                while True:
                    data = await websocket.receive_text()
                    with log_path.open("a", encoding="utf-8") as log_file:
                        log_file.write(data.strip() + "\n")
            except WebSocketDisconnect:
                print("[WS] Network log disconnected")

        @self.app.websocket("/redux")
        async def redux_endpoint(websocket: WebSocket):
            """WebSocket endpoint for Redux bridge state updates."""
            await websocket.accept()
            print("[WS] Redux bridge connected")

            try:
                while True:
                    data = await websocket.receive_text()
                    parsed = self._redux_handler.process_message(data)
                    if parsed is not None and self._state_manager is not None:
                        self._state_manager.apply_redux_state(parsed)
            except WebSocketDisconnect:
                print("[WS] Redux bridge disconnected")

    async def broadcast_state(self, state: AppGameState):
        """Broadcast state update to all clients."""
        self._current_state = state
        await self.manager.broadcast(state.to_dict())

    def on_state_change(self, state: AppGameState):
        """Callback for state changes (sync wrapper for cross-thread calls)."""
        self._current_state = state

        payload = state.to_dict()
        if self._should_compute_coach(state):
            try:
                write_trace = state.stage != self._last_coach_stage
                coach_payload = self._compute_coach_payload(state, write_trace=write_trace)
                self._last_coach_payload = coach_payload
                self._last_coach_compute_mono = time.monotonic()
                self._last_coach_stage = state.stage
            except Exception as e:
                self._last_coach_payload = {
                    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "error": str(e),
                }
            payload["coach"] = self._last_coach_payload
        elif self._last_coach_payload is not None and state.is_in_game:
            payload["coach"] = self._last_coach_payload

        self._current_payload = payload

        # Schedule broadcast in the server's event loop (thread-safe)
        if self._event_loop and self._event_loop.is_running():
            # Use run_coroutine_threadsafe for cross-thread async scheduling
            future = asyncio.run_coroutine_threadsafe(
                self.manager.broadcast(payload), self._event_loop
            )

            # Optional: log errors from the broadcast
            def handle_broadcast_error(f):
                try:
                    f.result()
                except Exception as e:
                    print(f"[WS] Broadcast error: {e}")

            future.add_done_callback(handle_broadcast_error)
        else:
            print("[WS] Warning: No event loop available for broadcast")

    def run(self):
        """Run the server (blocking)."""
        print(f"[SERVER] Starting on http://{self.host}:{self.port}")
        print(f"[SERVER] Overlay: http://{self.host}:{self.port}/overlay")
        print(f"[SERVER] WebSocket: ws://{self.host}:{self.port}/ws")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")

    async def run_async(self):
        """Run the server asynchronously."""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
