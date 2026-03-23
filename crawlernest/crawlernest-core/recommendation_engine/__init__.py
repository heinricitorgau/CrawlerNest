from .config import RecommendationConfig, default_recommendation_config
from .engine import RuleBasedRecommender, recommend_universities
from .repository import RecommendationRepository
from .types import (
    RecommendationCandidate,
    RecommendationQuery,
    RecommendationResult,
    RecommendationScoreBreakdown,
)

__all__ = [
    "RecommendationCandidate",
    "RecommendationConfig",
    "RecommendationQuery",
    "RecommendationRepository",
    "RecommendationResult",
    "RecommendationScoreBreakdown",
    "RuleBasedRecommender",
    "default_recommendation_config",
    "recommend_universities",
]
