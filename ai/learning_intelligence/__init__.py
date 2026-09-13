"""
Learning Intelligence & Decision Engine package.

Exports the core enums, models, metrics, evaluator, recommendations, contracts,
and decision engine orchestrators for the Adaptive Learning Coach.
"""

from .enums import (
    DecisionType,
    DifficultyLevel,
    ScoreTrend,
    SubStrategy,
    ReasonCode,
)
from .models import (
    LearnerContext,
    PerformanceMetrics,
    LearningAssessment,
    LearningDecision,
)
from .metrics import (
    calculate_historical_average,
    calculate_mastery_score,
    calculate_score_trend,
    calculate_consecutive_failures,
    calculate_consistency_index,
    extract_topic_strengths_and_gaps,
    compute_performance_metrics,
)
from .evaluator import (
    evaluate_learner_state,
    create_learning_assessment,
)
from .recommendations import (
    DEFAULT_CURRICULUM,
    get_next_difficulty,
    get_lower_difficulty,
    get_next_topic,
    generate_action_recommendation,
    generate_fallback_coaching_narrative,
)
from .contracts import (
    build_agent_prompt_context,
    validate_and_guardrail_ai_decision,
)
from .decision_engine import (
    evaluate_and_decide,
    evaluate_deterministic,
)

__all__ = [
    # Enums
    "DecisionType",
    "DifficultyLevel",
    "ScoreTrend",
    "SubStrategy",
    "ReasonCode",
    # Models
    "LearnerContext",
    "PerformanceMetrics",
    "LearningAssessment",
    "LearningDecision",
    # Metrics
    "calculate_historical_average",
    "calculate_mastery_score",
    "calculate_score_trend",
    "calculate_consecutive_failures",
    "calculate_consistency_index",
    "extract_topic_strengths_and_gaps",
    "compute_performance_metrics",
    # Evaluator
    "evaluate_learner_state",
    "create_learning_assessment",
    # Recommendations
    "DEFAULT_CURRICULUM",
    "get_next_difficulty",
    "get_lower_difficulty",
    "get_next_topic",
    "generate_action_recommendation",
    "generate_fallback_coaching_narrative",
    # Contracts & Guardrails
    "build_agent_prompt_context",
    "validate_and_guardrail_ai_decision",
    # Decision Engine Orchestrators
    "evaluate_and_decide",
    "evaluate_deterministic",
]
