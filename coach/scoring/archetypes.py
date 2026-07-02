from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from coach.artifacts import runtime_outputs_dir
from coach.state import GameState


def _token_from_api_name(api_name: str) -> str:
    return api_name.split("_", 1)[-1] if "_" in api_name else api_name


def _to_item_id(token: str) -> str:
    s = token.strip()
    if not s:
        return s
    if s.startswith("TFT_") or s.startswith("TFT16_"):
        return s
    return f"TFT_Item_{s}"


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None
    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except (ValueError, TypeError):
            return None
    return None


@dataclass(frozen=True, slots=True)
class ArchetypeBuild:
    unit_id: str
    items: tuple[str, ...]
    games: Optional[int] = None
    avg_placement: Optional[float] = None
    place_change: Optional[float] = None


@dataclass(frozen=True, slots=True)
class Archetype:
    archetype_id: str
    name: str
    tier: str
    units: tuple[str, ...]
    traits: tuple[str, ...]
    builds: tuple[ArchetypeBuild, ...] = ()
    top4_rate: Optional[float] = None
    avg_placement: Optional[float] = None


@dataclass(frozen=True, slots=True)
class ArchetypeMatch:
    archetype: Archetype
    similarity: float
    unit_jaccard: float
    trait_overlap: float


def _default_comps_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "meta" / "comps.json"


def _default_archetype_artifact_path() -> Path:
    return runtime_outputs_dir() / "archetypes.json"


def _fallback_perf_reference_path() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge-base" / "performance_reference.json"


class ArchetypeLibrary:
    def __init__(self, comps_path: Optional[Path] = None):
        self._comps_path = comps_path or _default_comps_path()
        self._artifact_path = _default_archetype_artifact_path()
        self._archetypes: Optional[tuple[Archetype, ...]] = None

    def _load(self) -> tuple[Archetype, ...]:
        if self._archetypes is not None:
            return self._archetypes

        archetypes: list[Archetype] = []
        if self._artifact_path.exists():
            try:
                data = json.loads(self._artifact_path.read_text(encoding="utf-8"))
                if int(data.get("schema_version") or 0) != 1:
                    raise ValueError("unsupported schema_version")
                for a in data.get("archetypes", []) or []:
                    stats = a.get("stats", {}) if isinstance(a.get("stats"), dict) else {}
                    builds_raw = a.get("builds", []) or []
                    builds: list[ArchetypeBuild] = []
                    if isinstance(builds_raw, list):
                        for b in builds_raw[:25]:
                            if not isinstance(b, dict):
                                continue
                            unit_id = b.get("unit") or b.get("unit_id") or ""
                            if not isinstance(unit_id, str) or not unit_id:
                                continue
                            items = b.get("items", []) or []
                            if not isinstance(items, list):
                                items = []
                            items_out = tuple(
                                str(x) for x in items if isinstance(x, str) and x.strip()
                            )
                            if not items_out:
                                continue
                            builds.append(
                                ArchetypeBuild(
                                    unit_id=unit_id,
                                    items=items_out,
                                    games=_as_int(b.get("games")),
                                    avg_placement=_as_float(b.get("avg_placement")),
                                    place_change=_as_float(b.get("place_change")),
                                )
                            )
                    archetypes.append(
                        Archetype(
                            archetype_id=str(a.get("archetype_id", a.get("name", "unknown"))),
                            name=str(a.get("name", "unknown")),
                            tier=str(a.get("tier", "C")),
                            units=tuple(a.get("units", []) or []),
                            traits=tuple(a.get("traits", []) or []),
                            builds=tuple(builds),
                            top4_rate=float(stats.get("top4_rate"))
                            if stats.get("top4_rate") is not None
                            else None,
                            avg_placement=float(stats.get("avg_placement"))
                            if stats.get("avg_placement") is not None
                            else None,
                        )
                    )
            except (OSError, ValueError, KeyError, TypeError):
                # Fall back to other sources if artifact is missing/incompatible.
                pass

        # comps.json is a fallback source when runtime artifact is unavailable.
        if not archetypes and self._comps_path.exists():
            try:
                data = json.loads(self._comps_path.read_text(encoding="utf-8"))
                for comp in data.get("comps", []) or []:
                    units = tuple(comp.get("units", []) or [])
                    token_to_api = {
                        _token_from_api_name(u): u for u in units if isinstance(u, str) and u
                    }
                    traits = tuple(
                        t.get("name")
                        for t in (comp.get("traits", []) or [])
                        if isinstance(t, dict) and t.get("name")
                    )
                    builds: list[ArchetypeBuild] = []
                    for b in (comp.get("builds", []) or [])[:25]:
                        if not isinstance(b, dict):
                            continue
                        unit_token = b.get("unit")
                        unit_id = None
                        if isinstance(unit_token, str) and unit_token:
                            unit_id = token_to_api.get(unit_token)
                            if unit_id is None:
                                unit_id = (
                                    unit_token
                                    if unit_token.startswith("TFT")
                                    else f"TFT16_{unit_token}"
                                )

                        items_out: list[str] = []
                        for it in b.get("items", []) or []:
                            if isinstance(it, str) and it.strip():
                                items_out.append(_to_item_id(it))

                        if unit_id and items_out:
                            builds.append(
                                ArchetypeBuild(
                                    unit_id=unit_id,
                                    items=tuple(items_out),
                                    games=_as_int(b.get("games")),
                                    avg_placement=_as_float(b.get("avg_placement")),
                                    place_change=_as_float(b.get("place_change")),
                                )
                            )
                    archetypes.append(
                        Archetype(
                            archetype_id=str(comp.get("cluster_id", comp.get("name", "unknown"))),
                            name=str(comp.get("name", "unknown")),
                            tier=str(comp.get("tier", "C")),
                            units=units,
                            traits=traits,
                            builds=tuple(builds),
                            top4_rate=float(comp.get("top4_rate"))
                            if comp.get("top4_rate") is not None
                            else None,
                            avg_placement=float(comp.get("avg_placement"))
                            if comp.get("avg_placement") is not None
                            else None,
                        )
                    )
            except (OSError, ValueError, KeyError, TypeError):
                # Fall through to perf-reference fallback.
                pass

        # Fallback: small hand-written archetype list.
        if not archetypes:
            perf_path = _fallback_perf_reference_path()
            if perf_path.exists():
                data = json.loads(perf_path.read_text(encoding="utf-8"))
                for comp in data.get("comp_archetypes", []) or []:

                    def _to_api_like(name: str) -> str:
                        # Best-effort conversion for fallback artifacts.
                        cleaned = name.replace("'", "").replace(" ", "").replace("&", "")
                        return f"TFT16_{cleaned}"

                    archetypes.append(
                        Archetype(
                            archetype_id=str(comp.get("id", comp.get("name", "unknown"))),
                            name=str(comp.get("name", "unknown")),
                            tier="?",
                            units=tuple(_to_api_like(u) for u in (comp.get("key_units") or [])),
                            traits=tuple(comp.get("core_traits") or []),
                        )
                    )

        self._archetypes = tuple(archetypes)
        return self._archetypes

    def closest(self, state: GameState, top_n: int = 3) -> list[ArchetypeMatch]:
        board_units = {u.champion_id for u in state.board if u.location == "board"}
        state_traits = set(state.traits_dict().keys())

        matches: list[ArchetypeMatch] = []
        for arch in self._load():
            arch_units = set(arch.units)
            if not arch_units:
                continue
            inter = len(board_units & arch_units)
            union = len(board_units | arch_units)
            unit_jaccard = inter / union if union else 0.0

            arch_traits = set(arch.traits)
            trait_inter = len(state_traits & arch_traits)
            trait_overlap = trait_inter / len(arch_traits) if arch_traits else 0.0

            similarity = 0.70 * unit_jaccard + 0.30 * trait_overlap

            # Small playstyle prior: prefer late-game AP/utility carries.
            for carry in ("TFT16_Fiddlesticks", "TFT16_Ornn", "TFT16_Ryze"):
                if carry in arch_units:
                    similarity += 0.03

            similarity = min(max(similarity, 0.0), 1.0)
            matches.append(
                ArchetypeMatch(
                    archetype=arch,
                    similarity=similarity,
                    unit_jaccard=unit_jaccard,
                    trait_overlap=trait_overlap,
                )
            )

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[: max(0, int(top_n))]

    def closest_archetypes(self, state: GameState, top_n: int = 3) -> list[ArchetypeMatch]:
        return self.closest(state, top_n=top_n)

    def alignment(self, state: GameState) -> tuple[float, Optional[str]]:
        best = self.closest(state, top_n=1)
        if not best:
            return 0.0, None
        return best[0].similarity, best[0].archetype.name

    def suggest_carry_candidates(self, state: GameState, top_n: int = 3) -> list[str]:
        matches = self.closest(state, top_n=3)
        out: list[str] = []
        for m in matches:
            for cid in m.archetype.units:
                if cid in out:
                    continue
                out.append(cid)
                if len(out) >= int(top_n):
                    return out
        return out

    def suggest_items_for_archetype(self, archetype_id: str) -> list[str]:
        weights: dict[str, float] = {}
        for arch in self._load():
            if arch.archetype_id != archetype_id:
                continue
            for b in arch.builds:
                w = float(b.games) if b.games is not None else 1.0
                for it in b.items:
                    weights[it] = weights.get(it, 0.0) + w

        if not weights:
            return []

        ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
        return [it for it, _ in ranked]
