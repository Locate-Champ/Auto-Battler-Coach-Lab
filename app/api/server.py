"""
Auto-Battler Coach API Server
Serves model predictions and recommendations to the frontend
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.requests import Request

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.api.deps import get_placement_model, get_recommender  # noqa: F401
from src.models import PlacementModel, TFTRecommender

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup, release on shutdown. Exits on failure."""
    _log.info("Loading Auto-Battler Coach models...")

    data_dir = Path(__file__).parent.parent.parent

    try:
        recommender = TFTRecommender(str(data_dir))
    except Exception:
        _log.critical("Failed to load TFTRecommender", exc_info=True)
        sys.exit(1)

    try:
        placement_model = PlacementModel(str(data_dir))
        X, y, _ = placement_model.prepare_data()
        placement_model.train(X, y, model_type="gradient_boosting")
    except Exception:
        _log.critical("Failed to load PlacementModel", exc_info=True)
        sys.exit(1)

    app.state.recommender = recommender
    app.state.placement_model = placement_model
    _log.info("All models loaded, server ready")

    yield

    del app.state.recommender
    del app.state.placement_model
    _log.info("Server shutdown complete, resources released")


app = FastAPI(title="Auto-Battler Coach API", version="1.0.0", lifespan=lifespan)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _log.exception("Unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An internal error occurred",
            "status": 500,
        },
    )


# ============== Data Models ==============


class Unit(BaseModel):
    name: str
    star: int = 1
    items: List[str] = []
    row: Optional[int] = None
    col: Optional[int] = None


class BoardState(BaseModel):
    units: List[Unit]
    stage: int = 3
    gold: int = 50
    level: int = 6
    hp: int = 100


class CompCount(BaseModel):
    name: str
    count: int


class AugmentFitRequest(BaseModel):
    traits: List[str]
    trait_frequency: Dict[str, int] = {}
    total_comps: int = 0
    top_n: int = 3


# ============== API Endpoints ==============


@app.get("/")
async def root():
    return {"status": "ok", "message": "Auto-Battler Coach API running"}


@app.get("/api/stats")
async def get_stats(
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Get personal performance stats"""
    # Get carry stats
    carry_stats = []
    for carry, stats in recommender.personal_carry_stats.items():
        games = stats.get("games", 0)
        if games >= 3:
            top4_rate = stats.get("top4_rate", 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace("%", ""))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            carry_stats.append({"name": carry, "games": games, "top4_rate": round(top4_rate, 1)})

    carry_stats.sort(key=lambda x: -x["top4_rate"])

    # Get trait stats
    trait_stats = []
    for trait, stats in recommender.personal_trait_stats.items():
        games = stats.get("games", 0)
        if games >= 3:
            top4_rate = stats.get("top4_rate", 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace("%", ""))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            trait_stats.append({"name": trait, "games": games, "top4_rate": round(top4_rate, 1)})

    trait_stats.sort(key=lambda x: -x["top4_rate"])

    return {"carries": carry_stats[:15], "traits": trait_stats[:15], "total_games": 163}


@app.get("/api/comps/{stage}")
async def get_stage_comps(
    stage: int,
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Get best comps for a stage"""
    comps = recommender.get_best_early_comps(stage, top_n=5)
    return {"stage": stage, "comps": comps}


@app.get("/api/meta-comps")
async def get_meta_comps(limit: int = 10):
    """Get current meta compositions from tactics.tools data"""
    data_dir = Path(__file__).parent.parent.parent
    comps_file = data_dir / "data" / "meta" / "comps.json"
    timestamp_file = data_dir / "data" / "meta" / "last_updated.json"

    if not comps_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Meta data not available. Add local data/meta/comps.json to enable this endpoint.",
        )

    with open(comps_file, "r") as f:
        data = json.load(f)

    # Get last updated timestamp
    last_updated = None
    if timestamp_file.exists():
        with open(timestamp_file, "r") as f:
            timestamp_data = json.load(f)
            last_updated = timestamp_data.get("last_updated")

    # Return top N comps with metadata
    return {
        "patch": data.get("patch", "unknown"),
        "total_games": data.get("total_games", 0),
        "last_updated": last_updated,
        "comps": data.get("comps", [])[:limit],
    }


@app.get("/api/early-comps")
async def get_early_comps(limit: int = 20):
    """Get early game compositions with transition links to late game comps"""
    data_dir = Path(__file__).parent.parent.parent
    early_file = data_dir / "data" / "meta" / "early_comps.json"

    if not early_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Early comps data not available. Add local data/meta/early_comps.json to enable this endpoint.",
        )

    with open(early_file, "r") as f:
        data = json.load(f)

    # Return early comps with transition data
    return {
        "stage": data.get("stage", "stage-2"),
        "source": data.get("source", "metatft"),
        "total_comps": data.get("total_comps", 0),
        "total_matchups": data.get("total_matchups", 0),
        "overall_stats": data.get("overall_stats", {}),
        "comps": data.get("comps", [])[:limit],
    }


@app.get("/api/augments")
async def get_augments(
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
    tier: Optional[str] = None,
    rarity: Optional[str] = None,
):
    """Get augment recommendations"""
    augments = recommender.get_augment_recommendations(rarity=rarity, top_n=20)

    if tier:
        augments = [a for a in augments if a["tier"] == tier.upper()]

    return {"augments": augments}


@app.post("/api/augment-fit")
async def get_augment_fit(
    request: AugmentFitRequest,
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Get augment fit rankings for a trait set."""
    ranked = recommender.get_augment_fit(
        traits=request.traits,
        trait_frequency=request.trait_frequency,
        total_comps=request.total_comps,
        top_n=request.top_n,
    )

    return {"augments": ranked}


@app.post("/api/recommend")
async def get_recommendations(
    board: BoardState,
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Get recommendations for current board state"""
    # Convert units to format expected by recommender
    units = [{"name": u.name, "star": u.star, "items": u.items} for u in board.units]

    recs = recommender.recommend_for_board(
        current_units=units, stage=board.stage, available_gold=board.gold
    )

    return recs


@app.post("/api/analyze")
async def analyze_board(
    board: BoardState,
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Analyze board and return detailed breakdown"""
    units = [{"name": u.name, "star": u.star, "items": u.items} for u in board.units]
    analysis = recommender.analyze_board(units)

    return analysis


@app.get("/api/priority-units")
async def get_priority_units(
    recommender: Annotated[TFTRecommender, Depends(get_recommender)],
):
    """Get priority units to look for based on personal stats"""
    priority = []
    for carry, stats in recommender.personal_carry_stats.items():
        games = stats.get("games", 0)
        if games >= 3:
            top4_rate = stats.get("top4_rate", 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace("%", ""))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            if top4_rate >= 50:
                champ_info = recommender.champions.get(carry, {})
                priority.append(
                    {
                        "name": carry,
                        "cost": champ_info.get("cost", 0),
                        "top4_rate": round(top4_rate, 1),
                        "games": games,
                    }
                )

    priority.sort(key=lambda x: (-x["top4_rate"], -x["games"]))
    return {"units": priority[:10]}


@app.get("/api/items")
async def get_item_suggestions():
    """Get item build/avoid suggestions based on personal data"""
    local_file = (
        Path(__file__).parent.parent.parent
        / "data"
        / "local"
        / "personal"
        / "item_performance_corrected.csv"
    )
    raise HTTPException(
        status_code=501,
        detail=(
            "Item suggestions require local data and are not available by default. "
            f"Expected local file: {local_file}"
        ),
    )


@app.post("/api/lobby")
async def update_lobby(comp_counts: List[CompCount]):
    """Update lobby tracker and get adjusted recommendations"""
    # Convert to dict
    counts = {c.name: c.count for c in comp_counts}

    # Adjust scores based on contestation
    # This would integrate with the recommender
    return {"received": counts, "message": "Lobby updated"}


def main():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
