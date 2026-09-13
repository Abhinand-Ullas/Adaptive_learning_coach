"""
Comprehensive Test Suite for Learning Intelligence & Decision Engine.

Validates the 10 critical operational scenarios for Member 2:
1. Repeated low scores -> REINFORCE
2. High & improving scores -> ADVANCE
3. Moderate scores with concept errors -> MENTOR
4. Isolated anomaly (one bad score for strong student) -> MENTOR (no demotion)
5. Fatigue circuit breaker (3+ consecutive failures) -> MENTOR (fatigue intervention)
6. Insufficient historical data (cold start) -> Safe baseline evaluation
7. Conflicting performance signals -> High score volatility handling
8. Missing optional fields -> Graceful default handling
9. Score boundary analysis -> Strict threshold adherence (59% vs 60%, 79% vs 80%)
10. AI Guardrail & Crash Recovery -> Rejection of hallucinated decisions and API failure fallback
"""

import pytest
from ai.learning_intelligence import (
    LearnerContext,
    PerformanceMetrics,
    LearningAssessment,
    LearningDecision,
    DecisionType,
    DifficultyLevel,
    ScoreTrend,
    SubStrategy,
    ReasonCode,
    compute_performance_metrics,
    create_learning_assessment,
    evaluate_learner_state,
    evaluate_and_decide,
    evaluate_deterministic,
    generate_action_recommendation,
    generate_fallback_coaching_narrative,
)


def test_case_1_repeated_low_scores_reinforce():
    """Case 1: Repeated low scores with declining trend triggers REINFORCE (under 3 failures)."""
    ctx = LearnerContext(
        student_id="student_101",
        current_topic="Functions",
        current_difficulty=DifficultyLevel.BEGINNER,
        current_score=40.0,
        score_history=[65.0, 50.0],  # 2 consecutive failures (50, 40)
        attempt_count=3,
        topic_scores={"return_values": 35.0, "arguments": 45.0},
    )
    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.REINFORCE
    assert decision.strategy in [SubStrategy.TARGETED_DRILL, SubStrategy.DIFFICULTY_DOWNGRADE]
    assert ReasonCode.LOW_RECENT_SCORE in decision.reason_codes
    assert "return_values" in decision.action_payload["focus_topics"]
    assert decision.suggested_action in ["ASSIGN_DRILL", "DOWNGRADE_DIFFICULTY_AND_DRILL"]


def test_case_2_high_and_improving_scores_advance():
    """Case 2: High, consistent, and improving scores trigger ADVANCE."""
    ctx = LearnerContext(
        student_id="student_102",
        current_topic="Control Flow",
        current_difficulty=DifficultyLevel.BEGINNER,
        current_score=92.0,
        score_history=[82.0, 88.0],
        attempt_count=3,
        topic_scores={"if_statements": 95.0, "boolean_logic": 90.0},
    )
    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.ADVANCE
    assert decision.strategy in [SubStrategy.DIFFICULTY_UPGRADE, SubStrategy.NEXT_TOPIC_UNLOCK]
    assert decision.target_difficulty == DifficultyLevel.INTERMEDIATE
    assert ReasonCode.MASTERY_ACHIEVED in decision.reason_codes
    assert decision.suggested_action == "UPGRADE_DIFFICULTY"


def test_case_3_moderate_scores_repeated_mistakes_mentor():
    """Case 3: Moderate scores (60-79%) with repeated mistake tags trigger MENTOR."""
    ctx = LearnerContext(
        student_id="student_103",
        current_topic="Loops",
        current_difficulty=DifficultyLevel.BEGINNER,
        current_score=70.0,
        score_history=[65.0, 72.0],
        attempt_count=3,
        repeated_mistake_tags=["OFF_BY_ONE", "INFINITE_LOOP"],
    )
    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.MENTOR
    assert decision.strategy in [SubStrategy.HINT_SCAFFOLDING, SubStrategy.CONCEPTUAL_EXPLANATION]
    assert decision.suggested_action == "START_MENTORING_SESSION"
    assert "Loops" in decision.coaching_narrative


def test_case_4_isolated_anomaly_no_demotion():
    """Case 4: Single bad score for student with strong historical average triggers MENTOR (no demotion)."""
    ctx = LearnerContext(
        student_id="student_104",
        current_topic="Data Structures",
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        current_score=48.0,  # Sudden drop
        score_history=[88.0, 92.0, 85.0],  # Strong historical baseline (>75%)
        attempt_count=4,
    )
    decision = evaluate_deterministic(ctx)

    # Must NOT demote to REINFORCE; must protect student with MENTOR
    assert decision.decision == DecisionType.MENTOR
    assert decision.strategy == SubStrategy.HINT_SCAFFOLDING
    assert ReasonCode.ISOLATED_ANOMALY in decision.reason_codes
    assert decision.target_difficulty == DifficultyLevel.INTERMEDIATE  # Kept at intermediate level


def test_case_5_fatigue_circuit_breaker():
    """Case 5: 3+ consecutive failures trigger fatigue intervention instead of endless drills."""
    ctx = LearnerContext(
        student_id="student_105",
        current_topic="Recursion",
        current_difficulty=DifficultyLevel.BEGINNER,
        current_score=45.0,
        score_history=[52.0, 48.0],  # 3 consecutive scores < 60%
        attempt_count=3,
    )
    decision = evaluate_deterministic(ctx)

    # Fatigue breaker switches from REINFORCE to empathetic MENTOR
    assert decision.decision == DecisionType.MENTOR
    assert decision.strategy == SubStrategy.FATIGUE_INTERVENTION
    assert ReasonCode.FATIGUE_DETECTED in decision.reason_codes
    assert "breather" in decision.coaching_narrative.lower() or "persistence" in decision.coaching_narrative.lower()


def test_case_6_cold_start_insufficient_history():
    """Case 6: 1st attempt with no history handled safely with COLD_START flag."""
    ctx_high = LearnerContext(
        student_id="student_106_a",
        current_topic="Python Basics",
        current_score=85.0,
        score_history=[],  # Cold start
        attempt_count=1,
    )
    decision_high = evaluate_deterministic(ctx_high)
    assert decision_high.decision == DecisionType.ADVANCE
    assert ReasonCode.COLD_START in decision_high.reason_codes

    ctx_low = LearnerContext(
        student_id="student_106_b",
        current_topic="Python Basics",
        current_score=45.0,
        score_history=[],
        attempt_count=1,
    )
    decision_low = evaluate_deterministic(ctx_low)
    assert decision_low.decision == DecisionType.REINFORCE
    assert ReasonCode.COLD_START in decision_low.reason_codes


def test_case_7_conflicting_signals_volatility():
    """Case 7: High score swings (e.g. 40% then 90% then 55%) detected as high volatility."""
    ctx = LearnerContext(
        student_id="student_107",
        current_topic="Functions",
        current_score=68.0,
        score_history=[40.0, 95.0, 45.0],
        attempt_count=4,
    )
    metrics = compute_performance_metrics(ctx)
    assessment = create_learning_assessment(ctx)

    # High standard deviation should trigger volatility handling
    assert metrics.consistency_index > 18.0
    assert assessment.baseline_decision == DecisionType.MENTOR
    assert ReasonCode.HIGH_SCORE_VOLATILITY in assessment.reason_codes


def test_case_8_missing_optional_fields():
    """Case 8: Missing optional fields (time_spent=None, empty topic_scores) run with zero exceptions."""
    ctx = LearnerContext(
        student_id="student_108",
        current_topic="OOP",
        current_score=75.0,
        # Omit score_history, time_spent_seconds, topic_scores, repeated_mistake_tags
    )
    decision = evaluate_deterministic(ctx)

    assert decision is not None
    assert decision.student_id == "student_108"
    assert decision.action_payload is not None
    assert decision.coaching_narrative != ""


def test_case_9_boundary_score_analysis():
    """Case 9: Strict threshold adherence around boundaries (59% vs 60%, 79% vs 80%)."""
    # Boundary 59% (Failing) vs 60% (Passing/Moderate)
    ctx_59 = LearnerContext(student_id="b1", current_topic="Loops", current_score=59.0, score_history=[59.0])
    ctx_60 = LearnerContext(student_id="b2", current_topic="Loops", current_score=60.0, score_history=[60.0])

    d_59 = evaluate_deterministic(ctx_59)
    d_60 = evaluate_deterministic(ctx_60)

    assert d_59.decision == DecisionType.REINFORCE
    assert d_60.decision == DecisionType.MENTOR

    # Boundary 79% (Moderate/Mentor) vs 80% (Mastery/Advance)
    ctx_79 = LearnerContext(student_id="b3", current_topic="Loops", current_score=79.0, score_history=[79.0])
    ctx_80 = LearnerContext(student_id="b4", current_topic="Loops", current_score=80.0, score_history=[80.0])

    d_79 = evaluate_deterministic(ctx_79)
    d_80 = evaluate_deterministic(ctx_80)

    assert d_79.decision == DecisionType.MENTOR
    assert d_80.decision == DecisionType.ADVANCE


def test_case_10_ai_guardrail_override_and_crash_recovery():
    """Case 10: AI hallucination is rejected by guardrail, and API timeouts trigger seamless fallback."""
    failing_ctx = LearnerContext(
        student_id="student_110",
        current_topic="Recursion",
        current_score=25.0,
        score_history=[30.0, 28.0],
        attempt_count=3,
    )

    # 1. Hallucinating Gemini Agent says ADVANCE
    def mock_hallucinating_agent(prompt_context):
        assert prompt_context["student_id"] == "student_110"
        return {
            "decision": "ADVANCE",  # Hallucination!
            "confidence": 0.99,
            "coaching_narrative": "You are ready for the hardest problems!",
        }

    decision_overridden = evaluate_and_decide(failing_ctx, mock_hallucinating_agent)
    # The guardrail MUST reject ADVANCE
    assert decision_overridden.decision != DecisionType.ADVANCE
    assert decision_overridden.decision in [DecisionType.MENTOR, DecisionType.REINFORCE]

    # 2. Crashing Gemini Agent (TimeoutError / 504 / API quota)
    def mock_crashing_agent(prompt_context):
        raise TimeoutError("Gemini API timed out after 10000ms")

    decision_fallback = evaluate_and_decide(failing_ctx, mock_crashing_agent)
    # The engine MUST not crash and must produce a valid decision with empathetic coaching
    assert decision_fallback is not None
    assert decision_fallback.decision in [DecisionType.MENTOR, DecisionType.REINFORCE]
    assert len(decision_fallback.coaching_narrative) > 20
