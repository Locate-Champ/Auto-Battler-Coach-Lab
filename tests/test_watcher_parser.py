from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_parser_module():
    parser_path = Path(__file__).resolve().parents[1] / "app" / "watcher" / "parser.py"
    spec = importlib.util.spec_from_file_location("watcher_parser_module", parser_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_board_update_from_escaped_kv_payload() -> None:
    parser_module = _load_parser_module()
    parser = parser_module.LogParser()
    line = (
        '2026-01-23 19:20:53,124 [DBG] '
        '{"key":"tft_board","value":"{\\"cell_1\\":{\\"characterID\\":\\"TFT16_Ashe\\",\\"starLevel\\":2}}"}'
    )
    event = parser.parse_line(line)
    assert event is not None
    assert event.event_type == parser_module.EventType.BOARD_UPDATE
    assert event.data["board"]["cell_1"]["characterID"] == "TFT16_Ashe"
    assert event.data["board"]["cell_1"]["starLevel"] == 2


def test_parse_bench_update_from_escaped_kv_payload() -> None:
    parser_module = _load_parser_module()
    parser = parser_module.LogParser()
    line = (
        '2026-01-23 19:20:53,124 [DBG] '
        '{"key":"tft_bench","value":"{\\"slot_0\\":{\\"characterID\\":\\"TFT16_Leona\\",\\"starLevel\\":1}}"}'
    )
    event = parser.parse_line(line)
    assert event is not None
    assert event.event_type == parser_module.EventType.BENCH_UPDATE
    assert event.data["bench"]["slot_0"]["characterID"] == "TFT16_Leona"
    assert event.data["bench"]["slot_0"]["starLevel"] == 1


def test_parse_shop_update_from_escaped_kv_payload() -> None:
    parser_module = _load_parser_module()
    parser = parser_module.LogParser()
    line = (
        '2026-01-23 19:20:53,124 [DBG] '
        '{"key":"tft_shop","value":"{\\"slot_0\\":{\\"characterID\\":\\"TFT16_Ashe\\",\\"cost\\":1}}"}'
    )
    event = parser.parse_line(line)
    assert event is not None
    assert event.event_type == parser_module.EventType.SHOP_UPDATE
    assert event.data["shop"]["slot_0"]["characterID"] == "TFT16_Ashe"
    assert event.data["shop"]["slot_0"]["cost"] == 1


def test_parse_roster_update_from_escaped_kv_payload() -> None:
    parser_module = _load_parser_module()
    parser = parser_module.LogParser()
    line = (
        '2026-01-23 19:20:53,124 [DBG] '
        '{"key":"tft_roster","value":"[{\\"name\\":\\"player1\\",\\"hp\\":90}]"}'
    )
    event = parser.parse_line(line)
    assert event is not None
    assert event.event_type == parser_module.EventType.ROSTER_UPDATE
    assert event.data["roster"][0]["name"] == "player1"
    assert event.data["roster"][0]["hp"] == 90
