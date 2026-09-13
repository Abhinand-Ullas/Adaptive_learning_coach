"""
Data models and contract schemas for Learning Intelligence & Decision Engine.

Enforces strong typing across team boundaries:
- LearnerContext: Input from Member 3 (DB to Agent)
- PerformanceMetrics: Internal calculated metrics (Member 2)
- LearningAssessment: Assessment payload for Member 1 (Gemini Agent)
- LearningDecision: Final approved action for Member 4 (Action Handler / SQLite)
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator
from .enums import (
    DecisionType,
    DifficultyLevel,
    ScoreTrend,
    SubStrategy,
    ReasonCode,
)


class LearnerContext(BaseModel):
    """
    Input contract received from Member 3 (Input Validation).
    Contains raw student data retrieved from SQLite and validated.
    """
    student_id: str = Field(..., description="Unique identifier for the student")
    current_topic: str = Field(..., description="Current topic or module being studied")
    current_difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.BEGINNER,
        description="Current difficulty level of the module"
    )
    current_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Score on the most recent quiz attempt (0-100)"
    )
    score_history: List[float] = Field(
        default_factory=list,
        description="Chronological scores of previous quiz attempts"
    )
    attempt_count: int = Field(
        default=1,
        ge=1,
        description="Number of attempts on this topic including current"
    )
    topic_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Subtopic performance breakdown (e.g. {'loops': 45.0, 'syntax': 80.0})"
    )
    time_spent_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent on the current quiz attempt in seconds"
    )
    repeated_mistake_tags: List[str] = Field(
        default_factory=list,
        description="Concept tags of recurring errors (e.g. ['OFF_BY_ONE', 'SYNTAX'])"
    )

    @field_validator("score_history")
    @classmethod
    def validate_score_history(cls, v: List[float]) -> List[float]:
        for s in v:
            if not (0.0 <= s <= 100.0):
                raise ValueError(f"Score in score_history must be between 0.0 and 100.0, got {s}")
        return v

    def full_score_sequence(self) -> List[float]:
        """Returns the full chronological score sequence including the current score."""
        return self.score_history + [self.current_score]


class PerformanceMetrics(BaseModel):
    """
    Calculated features produced by Member 2's metrics engine (metrics.py).
    Translates raw scores into quantitative and pedagogical signals.
    """
    historical_average: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Unweighted mean of all past attempts"
    )
    mastery_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Exponential Moving Average (EWMA) favoring recent attempts"
    )
    score_trend: ScoreTrend = Field(
        ...,
        description="Performance trajectory: IMPROVING, STABLE, or DECLINING"
    )
    score_delta: float = Field(
        ...,
        description="Recent score difference (current_score - latest_previous_score)"
    )
    consecutive_failures: int = Field(
        default=0,
        ge=0,
        description="Count of consecutive attempts scoring below 60.0%"
    )
    consistency_index: float = Field(
        default=0.0,
        ge=0.0,
        description="Standard deviation of scores across attempts (lower is more consistent)"
    )
    recent_scores: List[float] = Field(
        default_factory=list,
        description="Chronological recent quiz scores"
    )
    weak_topics: List[str] = Field(
        default_factory=list,
        description="Subtopics scoring below 65.0%"
    )
    strong_topics: List[str] = Field(
        default_factory=list,
        description="Subtopics scoring >= 80.0%"
    )
    is_cold_start: bool = Field(
        default=False,
        description="True if this is the student's first attempt (no prior history)"
    )


class LearningAssessment(BaseModel):
    """
    Evaluation contract passed to Member 1 (AI Agent / Gemini Core).
    Contains metrics, deterministic baseline decision, reason codes,
    and allowed decisions to constrain Gemini prompting.
    """
    learner_id: str
    topic: str
    current_difficulty: DifficultyLevel
    metrics: PerformanceMetrics
    baseline_decision: DecisionType
    primary_strategy: SubStrategy
    allowed_decisions: List[DecisionType] = Field(
        default_factory=list,
        description="Boundaries for Gemini: agent is constrained to these decisions"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    identified_gaps: List[str] = Field(default_factory=list)
    recommended_topics: List[str] = Field(default_factory=list)

    def to_agent_payload(self) -> Dict[str, Any]:
        """
        Formats a clean, deduplicated dictionary for Member 1 in Step 2.
        Member 1 injects these keys directly into the Gemini prompt template.
        """
        # Prior attempts excluding the current score to prevent duplicate data
        past_scores = (
            [round(s, 1) for s in self.metrics.recent_scores[:-1]]
            if len(self.metrics.recent_scores) > 1
            else []
        )
        current = (
            round(self.metrics.recent_scores[-1], 1)
            if self.metrics.recent_scores
            else round(self.metrics.mastery_score, 1)
        )

        return {
            "student_id": self.learner_id,
            "topic": self.topic,
            "current_difficulty": self.current_difficulty.value,
            "current_score": current,
            "past_score_history": past_scores,
            "mastery_score": round(self.metrics.mastery_score, 1),
            "score_trend": self.metrics.score_trend.value,
            "score_delta": round(self.metrics.score_delta, 1),
            "consecutive_failures": self.metrics.consecutive_failures,
            "weak_topics": self.metrics.weak_topics,
            "strong_topics": self.metrics.strong_topics,
            "suggested_decision": self.baseline_decision.value,
            "allowed_decisions": [d.value for d in self.allowed_decisions],
            "primary_strategy": self.primary_strategy.value,
            "reason_codes": [r.value for r in self.reason_codes],
            "is_cold_start": self.metrics.is_cold_start,
        }

    def to_member1_format(self, time_spent_seconds: Optional[int] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Convenience adapter mapping Member 2 metrics to Member 1's exact prompt signature:
        build_user_prompt(learner_context: dict, performance_metrics: dict)
        """
        time_minutes = round(time_spent_seconds / 60.0, 1) if time_spent_seconds else 1.0
        
        learner_context = {
            "student_id": self.learner_id,
            "course_name": "Python Programming",
            "current_topic": self.topic,
        }
        performance_metrics = {
            "recent_score_avg": round(self.metrics.mastery_score, 1),
            "trend": self.metrics.score_trend.value.lower(),
            "attempts_on_current_topic": len(self.metrics.recent_scores),
            "completion_percentage": 100 if self.baseline_decision == DecisionType.ADVANCE else 50,
            "time_spent_minutes": time_minutes,
        }
        return learner_context, performance_metrics


class LearningDecision(BaseModel):
    """
    Final approved decision passed to Member 4 (Action Handler & Database Updater).
    Contains the validated pedagogical decision, difficulty mutation, and
    action instructions for SQLite and Streamlit UI.
    """
    student_id: str
    decision: DecisionType
    strategy: SubStrategy
    topic: str
    target_difficulty: DifficultyLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    coaching_narrative: str = Field(
        ...,
        description="Empathetic coaching message for the student (from Gemini or deterministic fallback)"
    )
    suggested_action: str = Field(
        ...,
        description="High-level action code for Member 4 (e.g. 'ASSIGN_DRILL', 'UPDATE_DIFFICULTY')"
    )
    action_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed execution parameters for Member 4 (e.g. {'focus_topic': 'Loops', 'question_count': 3})"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes into a clean dictionary for SQLite mutation and Streamlit rendering."""
        return {
            "student_id": self.student_id,
            "decision": self.decision.value,
            "strategy": self.strategy.value,
            "topic": self.topic,
            "target_difficulty": self.target_difficulty.value,
            "confidence": round(self.confidence, 2),
            "reason_codes": [r.value for r in self.reason_codes],
            "coaching_narrative": self.coaching_narrative,
            "suggested_action": self.suggested_action,
            "action_payload": self.action_payload,
        }
