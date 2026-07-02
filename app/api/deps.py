"""Dependency injection functions for the Auto-Battler Coach API."""

from fastapi import Request

from src.models import PlacementModel, TFTRecommender


def get_recommender(request: Request) -> TFTRecommender:
    """Return the recommender from app.state. Trusts lifespan guarantee."""
    return request.app.state.recommender


def get_placement_model(request: Request) -> PlacementModel:
    """Return the placement model from app.state. Trusts lifespan guarantee."""
    return request.app.state.placement_model
