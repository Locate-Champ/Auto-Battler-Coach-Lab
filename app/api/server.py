"""
TFT Coach API Server
Serves model predictions and recommendations to the frontend
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models import FeatureEngineer, PlacementModel, TFTRecommender
from src.metatft_parser import MetaTFTLogParser

app = FastAPI(title="TFT Coach API", version="1.0.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize models on startup
recommender = None
placement_model = None
parser = None


@app.on_event("startup")
async def startup():
    global recommender, placement_model, parser
    print("Loading TFT Coach models...")

    data_dir = Path(__file__).parent.parent.parent
    recommender = TFTRecommender(str(data_dir))
    placement_model = PlacementModel(str(data_dir))
    parser = MetaTFTLogParser()

    # Train placement model
    X, y, _ = placement_model.prepare_data()
    placement_model.train(X, y, model_type='gradient_boosting')

    print("Models loaded successfully!")


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


# ============== API Endpoints ==============

@app.get("/")
async def root():
    return {"status": "ok", "message": "TFT Coach API running"}


@app.get("/api/stats")
async def get_stats():
    """Get personal performance stats"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # Get carry stats
    carry_stats = []
    for carry, stats in recommender.personal_carry_stats.items():
        games = stats.get('games', 0)
        if games >= 3:
            top4_rate = stats.get('top4_rate', 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace('%', ''))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            carry_stats.append({
                'name': carry,
                'games': games,
                'top4_rate': round(top4_rate, 1)
            })

    carry_stats.sort(key=lambda x: -x['top4_rate'])

    # Get trait stats
    trait_stats = []
    for trait, stats in recommender.personal_trait_stats.items():
        games = stats.get('games', 0)
        if games >= 3:
            top4_rate = stats.get('top4_rate', 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace('%', ''))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            trait_stats.append({
                'name': trait,
                'games': games,
                'top4_rate': round(top4_rate, 1)
            })

    trait_stats.sort(key=lambda x: -x['top4_rate'])

    return {
        'carries': carry_stats[:15],
        'traits': trait_stats[:15],
        'total_games': 163
    }


@app.get("/api/comps/{stage}")
async def get_stage_comps(stage: int):
    """Get best comps for a stage"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    comps = recommender.get_best_early_comps(stage, top_n=5)
    return {'stage': stage, 'comps': comps}


@app.get("/api/augments")
async def get_augments(tier: Optional[str] = None, rarity: Optional[str] = None):
    """Get augment recommendations"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    augments = recommender.get_augment_recommendations(
        rarity=rarity,
        top_n=20
    )

    if tier:
        augments = [a for a in augments if a['tier'] == tier.upper()]

    return {'augments': augments}


@app.post("/api/recommend")
async def get_recommendations(board: BoardState):
    """Get recommendations for current board state"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # Convert units to format expected by recommender
    units = [
        {
            'name': u.name,
            'star': u.star,
            'items': u.items
        }
        for u in board.units
    ]

    recs = recommender.recommend_for_board(
        current_units=units,
        stage=board.stage,
        available_gold=board.gold
    )

    return recs


@app.post("/api/analyze")
async def analyze_board(board: BoardState):
    """Analyze board and return detailed breakdown"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    units = [{'name': u.name, 'star': u.star, 'items': u.items} for u in board.units]
    analysis = recommender.analyze_board(units)

    return analysis


@app.get("/api/priority-units")
async def get_priority_units():
    """Get priority units to look for based on personal stats"""
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")

    priority = []
    for carry, stats in recommender.personal_carry_stats.items():
        games = stats.get('games', 0)
        if games >= 3:
            top4_rate = stats.get('top4_rate', 0)
            if isinstance(top4_rate, str):
                top4_rate = float(top4_rate.replace('%', ''))
            elif top4_rate <= 1:
                top4_rate = top4_rate * 100

            if top4_rate >= 50:
                champ_info = recommender.champions.get(carry, {})
                priority.append({
                    'name': carry,
                    'cost': champ_info.get('cost', 0),
                    'top4_rate': round(top4_rate, 1),
                    'games': games
                })

    priority.sort(key=lambda x: (-x['top4_rate'], -x['games']))
    return {'units': priority[:10]}


@app.get("/api/items")
async def get_item_suggestions():
    """Get item build/avoid suggestions based on personal data"""
    # This would come from item_performance_corrected.csv
    # For now return placeholder
    return {
        'build': [
            {'name': 'Blue Buff', 'rate': 72},
            {'name': 'Morellonomicon', 'rate': 68},
            {'name': 'Jeweled Gauntlet', 'rate': 65},
            {'name': 'Rabadons', 'rate': 63}
        ],
        'avoid': [
            {'name': 'Infinity Edge', 'rate': 35},
            {'name': 'Giant Slayer', 'rate': 38},
            {'name': 'Last Whisper', 'rate': 40}
        ]
    }


@app.post("/api/lobby")
async def update_lobby(comp_counts: List[CompCount]):
    """Update lobby tracker and get adjusted recommendations"""
    # Convert to dict
    counts = {c.name: c.count for c in comp_counts}

    # Adjust scores based on contestation
    # This would integrate with the recommender
    return {'received': counts, 'message': 'Lobby updated'}


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
