from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _install_fastapi_stubs(monkeypatch) -> None:
    fastapi_mod = types.ModuleType("fastapi")

    class _FakeFastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def on_event(self, *args, **kwargs):
            def _decorator(fn):
                return fn
            return _decorator

        def get(self, *args, **kwargs):
            def _decorator(fn):
                return fn
            return _decorator

        def websocket(self, *args, **kwargs):
            def _decorator(fn):
                return fn
            return _decorator

    class _FakeWebSocket:
        async def accept(self):
            return None

        async def send_text(self, _message: str):
            return None

        async def send_json(self, _message):
            return None

        async def receive_text(self) -> str:
            return ""

    class _FakeWebSocketDisconnect(Exception):
        pass

    fastapi_mod.FastAPI = _FakeFastAPI
    fastapi_mod.WebSocket = _FakeWebSocket
    fastapi_mod.WebSocketDisconnect = _FakeWebSocketDisconnect
    monkeypatch.setitem(sys.modules, "fastapi", fastapi_mod)

    responses_mod = types.ModuleType("fastapi.responses")

    class _FakeHTMLResponse:
        def __init__(self, content: str):
            self.content = content

    responses_mod.HTMLResponse = _FakeHTMLResponse
    monkeypatch.setitem(sys.modules, "fastapi.responses", responses_mod)

    uvicorn_mod = types.ModuleType("uvicorn")

    class _FakeConfig:
        def __init__(self, *args, **kwargs):
            pass

    class _FakeServer:
        def __init__(self, *args, **kwargs):
            pass

        async def serve(self):
            return None

    def _fake_run(*args, **kwargs):
        return None

    uvicorn_mod.Config = _FakeConfig
    uvicorn_mod.Server = _FakeServer
    uvicorn_mod.run = _fake_run
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_mod)


def test_ingest_contract_parser_state_manager_to_websocket(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    parser_mod = _load_module("app.watcher.parser", repo_root / "app" / "watcher" / "parser.py")

    watcher_pkg = types.ModuleType("app.watcher")
    watcher_pkg.__path__ = []
    watcher_pkg.LogParser = parser_mod.LogParser
    watcher_pkg.GameEvent = parser_mod.GameEvent
    watcher_pkg.parser = parser_mod
    monkeypatch.setitem(sys.modules, "app.watcher", watcher_pkg)
    monkeypatch.setitem(sys.modules, "app.watcher.parser", parser_mod)

    _install_fastapi_stubs(monkeypatch)

    from app.state.state_manager import StateManager
    from coach.explain import validate_coach_payload

    websocket_mod = _load_module("ingest_contract_websocket", repo_root / "app" / "server" / "websocket.py")
    WebSocketServer = websocket_mod.WebSocketServer

    parser = parser_mod.LogParser()
    manager = StateManager()
    ws_server = WebSocketServer(state_manager=manager)
    manager.on_state_change(ws_server.on_state_change)

    lines = [
        "2026-01-23 19:20:50,001 TFT starting",
        "2026-01-23 19:20:51,001 [EVT] stage: 2-1",
        '2026-01-23 19:20:52,001 [DBG] {"key":"tft_board","value":"{\\"cell_8\\":{\\"name\\":\\"TFT16_Ashe\\",\\"level\\":\\"2\\",\\"item_1\\":\\"TFT_Item_InfinityEdge\\",\\"item_2\\":\\"\\",\\"item_3\\":\\"\\"}}"}',
        '2026-01-23 19:20:52,101 [DBG] {"key":"tft_bench","value":"{\\"slot_0\\":{\\"name\\":\\"TFT16_Leona\\",\\"level\\":\\"1\\",\\"item_1\\":\\"\\",\\"item_2\\":\\"\\",\\"item_3\\":\\"\\"}}"}',
        '2026-01-23 19:20:52,201 [DBG] {"key":"tft_shop","value":"{\\"slot_0\\":{\\"name\\":\\"TFT16_Ekko\\",\\"cost\\":\\"2\\"}}"}',
        '2026-01-23 19:20:52,301 [DBG] {"key":"tft_roster","value":"[{\\"summoner\\":\\"me\\",\\"localplayer\\":\\"1\\",\\"health\\":\\"92\\",\\"xp\\":\\"0\\"}]"}',
    ]

    for line in lines:
        event = parser.parse_line(line)
        assert event is not None
        manager.process_event(event)

    payload = ws_server._current_payload
    assert isinstance(payload, dict)
    assert payload["game_phase"] == "pvp"
    assert payload["player"]["name"] == "me"
    assert payload["player"]["health"] == 92

    board_units = payload["board_units"]
    assert len(board_units) == 1
    assert board_units[0]["character_id"] == "TFT16_Ashe"
    assert board_units[0]["stars"] == 2
    assert board_units[0]["position"] == {"row": 1, "col": 1}

    bench_units = payload["bench_units"]
    assert len(bench_units) == 1
    assert bench_units[0]["character_id"] == "TFT16_Leona"

    shop_units = payload["shop_units"]
    assert len(shop_units) == 1
    assert shop_units[0]["character_id"] == "TFT16_Ekko"
    assert shop_units[0]["cost"] == 2

    coach_payload = payload.get("coach")
    assert isinstance(coach_payload, dict)
    assert coach_payload.get("coach_payload_version") == 1
    assert isinstance(coach_payload.get("generated_at"), str)
    assert set((coach_payload.get("recommendations") or {}).keys()) == {"items", "position", "econ", "shop"}
    assert validate_coach_payload(coach_payload) == []
