"""
State Evaluator and Priority Triage Engine.

Implements the multi-tiered pedagogical decision framework:
- Tier 1: Fatigue breaker (consecutive failures >= 3 -> MENTOR)
- Tier 2: Cold start evaluation (first attempt)
- Tier 3: Isolated anomaly shield (single dip for strong student -> MENTOR)
- Tier 4: Mastery progression (>=80% + positive/stable trend -> ADVANCE)
- Tier 5: Targeted remediation (<60% -> REINFORCE)
- Tier 6: Intermediate scaffolding (60-79% -> MENTOR)
"""

from typing import Tuple, List
from .enums import (
    DecisionType,
    DifficultyLevel,
    ScoreTrend,
    SubStrategy,
    ReasonCode,
)
from .models import LearnerContext, PerformanceMetrics, LearningAssessment
from .metrics import compute_performance_metrics


def evaluate_learner_state(
    context: LearnerContext,
    metrics: PerformanceMetrics
) -> Tuple[DecisionType, SubStrategy, float, List[ReasonCode], List[DecisionType]]:
    """
    Evaluates learner metrics through priority triage tiers.
    
    Returns:
        (baseline_decision, primary_strategy, confidence, reason_codes, allowed_decisions)
    """
    # -------------------------------------------------------------
    # TIER 1: Fatigue Circuit Breaker
    # 3+ consecutive failures: Stop drill spam, switch to guidance
    # -------------------------------------------------------------
    if metrics.consecutive_failures >= 3:
        return (
            DecisionType.MENTOR,
            SubStrategy.FATIGUE_INTERVENTION,
            0.95,
            [ReasonCode.FATIGUE_DETECTED, ReasonCode.PERSISTENT_STRUGGLE],
            [DecisionType.MENTOR, DecisionType.REINFORCE],
        )

    # -------------------------------------------------------------
    # TIER 2: Cold Start Evaluation (1st attempt on this topic)
    # -------------------------------------------------------------
    if metrics.is_cold_start:
        if context.current_score >= 80.0:
            return (
                DecisionType.ADVANCE,
                SubStrategy.NEXT_TOPIC_UNLOCK,
                0.80,  # Conservative confidence on single attempt
                [ReasonCode.MASTERY_ACHIEVED, ReasonCode.COLD_START],
                [DecisionType.ADVANCE, DecisionType.MENTOR],
            )
        elif context.current_score < 60.0:
            return (
                DecisionType.REINFORCE,
                SubStrategy.TARGETED_DRILL,
                0.85,
                [ReasonCode.LOW_RECENT_SCORE, ReasonCode.COLD_START],
                [DecisionType.REINFORCE, DecisionType.MENTOR],
            )
        else:
            return (
                DecisionType.MENTOR,
                SubStrategy.CONCEPTUAL_EXPLANATION,
                0.80,
                [ReasonCode.COLD_START],
                [DecisionType.MENTOR, DecisionType.REINFORCE],
            )

    # -------------------------------------------------------------
    # TIER 3: Isolated Anomaly Shield
    # Single bad score (<60%) for student with prior history average >= 75%
    # Protects strong students from knee-jerk demotion on one bad attempt.
    # -------------------------------------------------------------
    prior_scores = context.score_history
    if len(prior_scores) >= 1:
        prior_avg = sum(prior_scores) / len(prior_scores)
        if context.current_score < 60.0 and prior_avg >= 75.0:
            return (
                DecisionType.MENTOR,
                SubStrategy.HINT_SCAFFOLDING,
                0.88,
                [ReasonCode.ISOLATED_ANOMALY, ReasonCode.LOW_RECENT_SCORE],
                [DecisionType.MENTOR, DecisionType.REINFORCE],
            )

    # -------------------------------------------------------------
    # TIER 4: Mastery Progression (ADVANCE)
    # Mastery >= 80% and current score >= 78% with non-declining trend
    # -------------------------------------------------------------
    if (
        metrics.mastery_score >= 80.0
        and context.current_score >= 78.0
        and metrics.score_trend != ScoreTrend.DECLINING
    ):
        if metrics.mastery_score >= 95.0:
            strategy = SubStrategy.ACCELERATED_CHALLENGE
        elif context.current_difficulty == DifficultyLevel.ADVANCED:
            strategy = SubStrategy.NEXT_TOPIC_UNLOCK
        else:
            strategy = SubStrategy.DIFFICULTY_UPGRADE

        confidence = round(min(0.98, 0.85 + (metrics.mastery_score - 80.0) * 0.007), 2)
        return (
            DecisionType.ADVANCE,
            strategy,
            confidence,
            [ReasonCode.MASTERY_ACHIEVED],
            [DecisionType.ADVANCE],  # Constrain Gemini to ADVANCE
        )

    # -------------------------------------------------------------
    # TIER 5: Active Remediation Needed (REINFORCE)
    # Mastery < 60% OR (current < 60% and trend not improving)
    # -------------------------------------------------------------
    if (
        metrics.mastery_score < 60.0
        or (context.current_score < 60.0 and metrics.score_trend != ScoreTrend.IMPROVING)
    ):
        reasons = [ReasonCode.LOW_RECENT_SCORE]

        if metrics.score_trend == ScoreTrend.DECLINING:
            reasons.append(ReasonCode.DECLINING_TREND)

        if metrics.consecutive_failures >= 2:
            reasons.append(ReasonCode.PERSISTENT_STRUGGLE)

        if metrics.weak_topics:
            reasons.append(ReasonCode.TOPIC_DEFICIT)

        # Decide sub-strategy
        if metrics.consecutive_failures >= 2 and context.current_difficulty != DifficultyLevel.BEGINNER:
            strategy = SubStrategy.DIFFICULTY_DOWNGRADE
        elif metrics.weak_topics:
            strategy = SubStrategy.TARGETED_DRILL
        else:
            strategy = SubStrategy.TARGETED_DRILL

        confidence = round(min(0.95, 0.82 + (60.0 - metrics.mastery_score) * 0.003), 2)
        return (
            DecisionType.REINFORCE,
            strategy,
            confidence,
            reasons,
            [DecisionType.REINFORCE, DecisionType.MENTOR],
        )

    # -------------------------------------------------------------
    # TIER 6: Intermediate Zone / Volatility (MENTOR)
    # 60.0% <= score < 80.0% or erratic variance
    # -------------------------------------------------------------
    reasons = []
    if metrics.consistency_index > 18.0:
        reasons.append(ReasonCode.HIGH_SCORE_VOLATILITY)
        strategy = SubStrategy.WORKED_EXAMPLE
    elif context.repeated_mistake_tags:
        reasons.append(ReasonCode.PERSISTENT_STRUGGLE)
        strategy = SubStrategy.HINT_SCAFFOLDING
    else:
        strategy = SubStrategy.CONCEPTUAL_EXPLANATION

    if metrics.weak_topics:
        reasons.append(ReasonCode.TOPIC_DEFICIT)

    return (
        DecisionType.MENTOR,
        strategy,
        0.85,
        reasons,
        [DecisionType.MENTOR, DecisionType.REINFORCE],
    )


def create_learning_assessment(context: LearnerContext) -> LearningAssessment:
    """
    Step 1 & 2 coordinator for Member 2.
    Computes metrics from LearnerContext, runs state evaluation,
    and packages the final LearningAssessment ready for Member 1's Gemini prompt.
    """
    metrics = compute_performance_metrics(context)
    (
        decision,
        strategy,
        confidence,
        reasons,
        allowed_decisions,
    ) = evaluate_learner_state(context, metrics)

    return LearningAssessment(
        learner_id=context.student_id,
        topic=context.current_topic,
        current_difficulty=context.current_difficulty,
        metrics=metrics,
        baseline_decision=decision,
        primary_strategy=strategy,
        allowed_decisions=allowed_decisions,
        confidence=confidence,
        reason_codes=reasons,
        identified_gaps=metrics.weak_topics,
        recommended_topics=metrics.strong_topics,
    )
