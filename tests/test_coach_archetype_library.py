from __future__ import annotations

import json
from pathlib import Path

from coach.offline.build_archetypes import build_archetypes
from coach.scoring.archetypes import ArchetypeLibrary
from coach.state import GameState, PlayerState, UnitState


def _state_for_archetypes() -> GameState:
    player = PlayerState(level=7, hp=62, gold=28, win_streak=2, loss_streak=0)
    board = (
        UnitState(instance_id="u0", champion_id="TFT16_Fiddlesticks", star_level=2, items=(), position=(0, 3), location="board"),
        UnitState(instance_id="u1", champion_id="TFT16_Sion", star_level=2, items=(), position=(3, 3), location="board"),
    )
    return GameState(stage="4-2", player=player, board=board)


def test_archetype_library_is_stable_for_same_state() -> None:
    lib = ArchetypeLibrary()
    state = _state_for_archetypes()
    m1 = lib.closest(state, top_n=3)
    m2 = lib.closest(state, top_n=3)
    assert [(m.archetype.archetype_id, m.similarity) for m in m1] == [(m.archetype.archetype_id, m.similarity) for m in m2]


def test_archetype_library_missing_artifacts_degrades_gracefully(tmp_path: Path) -> None:
    lib = ArchetypeLibrary(comps_path=tmp_path / "missing_comps.json")
    lib._artifact_path = tmp_path / "missing_archetypes.json"
    state = _state_for_archetypes()
    out = lib.closest(state, top_n=3)
    assert isinstance(out, list)


def test_suggest_items_for_archetype_uses_builds_from_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "archetypes.json"
    artifact = {
        "schema_version": 1,
        "type": "coach_archetypes",
        "source": "test",
        "count": 1,
        "archetypes": [
            {
                "archetype_id": "arch1",
                "name": "Test Archetype",
                "tier": "S",
                "units": ["TFT16_TestUnit"],
                "traits": ["TestTrait"],
                "builds": [
                    {
                        "unit": "TFT16_TestUnit",
                        "items": ["TFT_Item_InfinityEdge", "TFT_Item_BrambleVest"],
                        "games": 100,
                    },
                    {
                        "unit": "TFT16_TestUnit",
                        "items": ["TFT_Item_BrambleVest", "TFT_Item_Redemption"],
                        "games": 50,
                    },
                ],
                "stats": {},
            }
        ],
    }
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    lib = ArchetypeLibrary(comps_path=tmp_path / "missing_comps.json")
    lib._artifact_path = artifact_path

    out = lib.suggest_items_for_archetype("arch1")
    assert out == ["TFT_Item_BrambleVest", "TFT_Item_InfinityEdge", "TFT_Item_Redemption"]


def test_build_archetypes_emits_builds_with_item_ids(tmp_path: Path) -> None:
    input_path = tmp_path / "comps.json"
    output_path = tmp_path / "archetypes.json"

    payload = {
        "comps": [
            {
                "cluster_id": "c1",
                "tier": "A",
                "name": "Comp1",
                "units": ["TFT16_Kaisa", "TFT16_Garen"],
                "traits": [{"name": "Foo", "count": 2}],
                "builds": [
                    {
                        "unit": "Kaisa",
                        "items": ["InfinityEdge", "TFT16_Item_ZaunEmblemItem"],
                        "games": 10,
                        "avg_placement": 3.2,
                        "place_change": -0.1,
                    },
                    {"unit": "Garen", "items": ["BrambleVest"], "games": "5"},
                    {"unit": "UnknownUnit", "items": ["Leviathan"], "games": 1},
                ],
            }
        ]
    }
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    out = build_archetypes(input_path, output_path)
    assert int(out.get("schema_version") or 0) == 1
    assert int(out.get("count") or 0) == 1

    arch = out["archetypes"][0]
    builds = arch["builds"]
    assert isinstance(builds, list)
    assert len(builds) == 3

    assert builds[0]["unit"] == "TFT16_Kaisa"
    assert builds[0]["items"] == ["TFT_Item_InfinityEdge", "TFT16_Item_ZaunEmblemItem"]

    assert builds[1]["unit"] == "TFT16_Garen"
    assert builds[1]["items"] == ["TFT_Item_BrambleVest"]

    assert builds[2]["unit"] == "TFT16_UnknownUnit"
    assert builds[2]["items"] == ["TFT_Item_Leviathan"]
