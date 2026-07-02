"""Tests for the Auto-Battler Coach API server.

Covers: lifespan loading, startup failure exit, dependency injection,
endpoint contracts, global exception handler, and static checks.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_recommender
from app.api.server import app


def _mock_lifespan_models():
    """Return patch context managers that mock model loading in the lifespan."""
    mock_recommender = MagicMock()
    mock_placement = MagicMock()
    mock_placement.prepare_data.return_value = (
        MagicMock(),
        MagicMock(),
        None,
    )
    mock_placement.train.return_value = None

    rec_patch = patch(
        "app.api.server.TFTRecommender",
        return_value=mock_recommender,
    )
    plc_patch = patch(
        "app.api.server.PlacementModel",
        return_value=mock_placement,
    )
    return rec_patch, plc_patch, mock_recommender, mock_placement


# ---------- 1. Lifespan loads models (GLBL-03) ----------


def test_lifespan_loads_models():
    """Lifespan populates app.state with both models."""
    rec_patch, plc_patch, mock_rec, mock_plc = _mock_lifespan_models()

    with rec_patch, plc_patch, TestClient(app) as client:
        assert app.state.recommender is mock_rec
        assert app.state.placement_model is mock_plc

        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------- 2. Startup failure exits (GLBL-04) ----------


def test_startup_failure_exits():
    """If TFTRecommender fails to load, the process calls sys.exit(1)."""
    mock_exit = MagicMock(side_effect=SystemExit(1))
    with (
        patch(
            "app.api.server.TFTRecommender",
            side_effect=FileNotFoundError("missing data"),
        ),
        patch("app.api.server.sys.exit", mock_exit),
    ):
        try:
            with TestClient(app):
                pass  # pragma: no cover -- never reached
        except (RuntimeError, OSError, SystemExit):
            pass  # TestClient may raise when lifespan fails

    mock_exit.assert_called_once_with(1)


def test_startup_failure_placement_model_exits():
    """If PlacementModel fails, the process calls sys.exit(1)."""
    mock_rec = MagicMock()
    mock_exit = MagicMock(side_effect=SystemExit(1))
    with (
        patch("app.api.server.TFTRecommender", return_value=mock_rec),
        patch(
            "app.api.server.PlacementModel",
            side_effect=RuntimeError("training crash"),
        ),
        patch("app.api.server.sys.exit", mock_exit),
    ):
        try:
            with TestClient(app):
                pass  # pragma: no cover
        except (RuntimeError, OSError, SystemExit):
            pass  # TestClient may raise when lifespan fails

    mock_exit.assert_called_once_with(1)


# ---------- 3. Deps return state objects ----------


def test_deps_return_injected_objects():
    """Dependency overrides supply mock models to endpoints."""
    mock_recommender = MagicMock()
    mock_recommender.personal_carry_stats = {}
    mock_recommender.personal_trait_stats = {}

    app.dependency_overrides[get_recommender] = lambda: mock_recommender
    try:
        rec_patch, plc_patch, _, _ = _mock_lifespan_models()
        with rec_patch, plc_patch, TestClient(app) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "carries" in data
            assert "traits" in data
    finally:
        app.dependency_overrides.clear()


# ---------- 4. Endpoint contracts unchanged ----------


def test_root_endpoint():
    """GET / returns status ok."""
    rec_patch, plc_patch, _, _ = _mock_lifespan_models()
    with rec_patch, plc_patch, TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "message" in body


def test_stats_endpoint_contract():
    """GET /api/stats returns carries, traits, total_games."""
    mock_recommender = MagicMock()
    mock_recommender.personal_carry_stats = {
        "Ahri": {"games": 5, "top4_rate": 0.6},
    }
    mock_recommender.personal_trait_stats = {
        "Sorcerer": {"games": 4, "top4_rate": 0.75},
    }

    app.dependency_overrides[get_recommender] = lambda: mock_recommender
    try:
        rec_patch, plc_patch, _, _ = _mock_lifespan_models()
        with rec_patch, plc_patch, TestClient(app) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert "carries" in body
            assert "traits" in body
            assert "total_games" in body
    finally:
        app.dependency_overrides.clear()


def test_lobby_endpoint_contract():
    """POST /api/lobby accepts CompCount list and returns 200."""
    rec_patch, plc_patch, _, _ = _mock_lifespan_models()
    with rec_patch, plc_patch, TestClient(app) as client:
        resp = client.post(
            "/api/lobby",
            json=[{"name": "Reroll Veigar", "count": 2}],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "received" in body
        assert "message" in body


# ---------- 5. Global exception handler ----------


def test_global_exception_handler():
    """Unhandled exceptions return structured JSON with error/detail/status."""

    def _broken_recommender():
        mock = MagicMock()
        mock.personal_carry_stats = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        # Force attribute access to raise
        type(mock).personal_carry_stats = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        return mock

    app.dependency_overrides[get_recommender] = _broken_recommender
    try:
        rec_patch, plc_patch, _, _ = _mock_lifespan_models()
        with rec_patch, plc_patch, TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 500
            body = resp.json()
            assert "error" in body
            assert "detail" in body
            assert "status" in body
    finally:
        app.dependency_overrides.clear()


# ---------- 6. Static check: no @app.on_event ----------


def test_no_on_event_in_server():
    """server.py must not contain any on_event usage (GLBL-03 static check)."""
    server_path = Path(__file__).parent.parent / "app" / "api" / "server.py"
    source_text = server_path.read_text()
    assert "on_event" not in source_text, "Found on_event in server.py -- should use lifespan"
