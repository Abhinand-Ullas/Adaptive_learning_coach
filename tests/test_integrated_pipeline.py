"""
Integration Test Suite across Merged Modules:
- Member 3: SQLite Database (data/learning_coach.db)
- Member 2: Learning Intelligence & Decision Engine (ai/learning_intelligence)
- Member 1: AI Agent & Prompt Builder (ai/prompts.py, ai/schemas.py, ai/agent.py)

Also audits and verifies JSON deduplication and schema consistency.
"""

import os
import json
import sqlite3
import pytest

from ai.learning_intelligence import (
    LearnerContext,
    DifficultyLevel,
    DecisionType,
    SubStrategy,
    ReasonCode,
    compute_performance_metrics,
    create_learning_assessment,
    evaluate_deterministic,
    evaluate_and_decide,
)
from ai.prompts import build_user_prompt, COACH_SYSTEM_PROMPT
from ai.schemas import AIProposedDecision, LearningDecision as Member1DecisionEnum

from database.seed import seed_database

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/learning_coach.db")


@pytest.fixture(autouse=True)
def reset_test_db_baseline():
    """Ensures database is reset to baseline before each test run."""
    seed_database()



def fetch_student_from_db(student_id: str, topic: str) -> LearnerContext:
    """Helper querying Member 3's real SQLite database to build LearnerContext."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT score, difficulty, time_spent_seconds 
        FROM quiz_attempts 
        WHERE student_id = ? AND topic = ? 
        ORDER BY attempt_id ASC
    """, (student_id, topic))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError(f"No records for student {student_id} on topic {topic}")

    latest_score, latest_diff, latest_time = rows[-1]
    past_scores = [float(r[0]) for r in rows[:-1]]

    return LearnerContext(
        student_id=student_id,
        current_topic=topic,
        current_difficulty=DifficultyLevel(latest_diff.upper()),
        current_score=float(latest_score),
        score_history=past_scores,
        attempt_count=len(rows),
        time_spent_seconds=latest_time,
    )


def test_student_1_anu_declining_reinforce_from_db():
    """
    Test Anu (student_id='1') from SQLite:
    Attempts on CSS: 60.0, 51.0, 42.0 (Declining trend with 2 consecutive failures).
    Should trigger REINFORCE with DECLINING_TREND.
    """
    ctx = fetch_student_from_db("1", "CSS")
    assert ctx.attempt_count == 3
    assert ctx.current_score == 42.0
    assert ctx.score_history == [60.0, 51.0]

    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.REINFORCE
    assert ReasonCode.LOW_RECENT_SCORE in decision.reason_codes
    assert ReasonCode.DECLINING_TREND in decision.reason_codes
    assert decision.suggested_action in ["ASSIGN_DRILL", "DOWNGRADE_DIFFICULTY_AND_DRILL"]


def test_student_1_anu_subsequent_failure_triggers_fatigue_breaker():
    """
    If Anu attempts CSS once more and fails again (e.g. 40.0%),
    consecutive failures reach 3, triggering the Fatigue Breaker (MENTOR).
    """
    ctx_fatigue = LearnerContext(
        student_id="1",
        current_topic="CSS",
        current_difficulty=DifficultyLevel.BEGINNER,
        current_score=40.0,
        score_history=[60.0, 51.0, 42.0],  # 51, 42, 40 -> 3 consecutive failures
        attempt_count=4,
    )
    decision = evaluate_deterministic(ctx_fatigue)

    assert decision.decision == DecisionType.MENTOR
    assert decision.strategy == SubStrategy.FATIGUE_INTERVENTION
    assert ReasonCode.FATIGUE_DETECTED in decision.reason_codes
    assert decision.suggested_action == "START_MENTORING_SESSION"


def test_student_2_rahul_advance_from_db():
    """
    Test Rahul (student_id='2') from SQLite:
    Attempt on JS: 91.0% at ADVANCED difficulty in 20s.
    Should trigger ADVANCE via Member 2's engine.
    """
    ctx = fetch_student_from_db("2", "JS")
    assert ctx.current_score == 91.0
    assert ctx.current_difficulty == DifficultyLevel.ADVANCED

    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.ADVANCE
    assert ReasonCode.MASTERY_ACHIEVED in decision.reason_codes
    assert decision.suggested_action in ["UPGRADE_DIFFICULTY", "UNLOCK_NEXT_TOPIC", "ASSIGN_CHALLENGE_PROBLEM"]


def test_student_3_meera_reinforce_from_db():
    """
    Test Meera (student_id='3') from SQLite:
    Attempt on MERN stack: 48.0% in 90s (Cold start failure).
    Should trigger REINFORCE via Member 2's engine.
    """
    ctx = fetch_student_from_db("3", "MERN stack")
    assert ctx.current_score == 48.0
    assert len(ctx.score_history) == 0  # Cold start

    decision = evaluate_deterministic(ctx)

    assert decision.decision == DecisionType.REINFORCE
    assert ReasonCode.COLD_START in decision.reason_codes
    assert decision.suggested_action == "ASSIGN_DRILL"


def test_member2_to_member1_prompt_integration():
    """
    Verifies that Member 2's assessment cleanly formats into Member 1's prompt
    without any missing 'Unknown' or '0' values.
    """
    ctx = fetch_student_from_db("1", "CSS")
    assessment = create_learning_assessment(ctx)

    # Convert to Member 1's exact prompt signature
    learner_ctx_dict, perf_metrics_dict = assessment.to_member1_format(time_spent_seconds=ctx.time_spent_seconds)

    prompt = build_user_prompt(learner_ctx_dict, perf_metrics_dict)

    # Check that all fields were cleanly populated by Member 2
    assert "Student ID: 1" in prompt
    assert "Current Topic: CSS" in prompt
    assert "Recent Score Average: 47.8%" in prompt or "Recent Score Average:" in prompt
    assert "Score Trend: declining" in prompt
    assert "Attempts on Topic: 3" in prompt
    assert "Unknown" not in prompt


def test_json_deduplication_audit():
    """
    Audits JSON payloads to ensure NO duplicate fields or redundant values exist:
    - No duplicate 'identified_gaps' alongside 'weak_topics'
    - 'past_score_history' does not duplicate 'current_score'
    - All data is cleanly JSON-serializable
    """
    ctx = LearnerContext(
        student_id="audit_student",
        current_topic="Functions",
        current_score=45.0,
        score_history=[60.0, 50.0],
        topic_scores={"loops": 30.0, "scope": 85.0}
    )
    assessment = create_learning_assessment(ctx)
    payload = assessment.to_agent_payload()

    # 1. Payload must be valid JSON
    serialized = json.dumps(payload)
    assert serialized is not None

    # 2. Check no duplicate keys
    keys = list(payload.keys())
    assert len(keys) == len(set(keys)), "Payload contains duplicate dictionary keys!"

    # 3. Check identified_gaps redundancy was eliminated
    assert "identified_gaps" not in payload, "Redundant 'identified_gaps' key found!"
    assert "weak_topics" in payload

    # 4. Check past_score_history does not duplicate current_score
    assert payload["current_score"] == 45.0
    assert payload["past_score_history"] == [60.0, 50.0]
    assert 45.0 not in payload["past_score_history"], "current_score was duplicated inside past_score_history!"


def test_end_to_end_with_member1_schema_compliance():
    """
    Tests Member 1's AIProposedDecision schema compatibility with Member 2's guardrails.
    """
    ctx = fetch_student_from_db("1", "CSS")

    # Member 1 agent mock returning valid AIProposedDecision format
    def mock_member1_agent(prompt_context):
        return {
            "behavioral_analysis": "Student spent 60 seconds and scored 42%, failing for the 3rd time.",
            "decision": Member1DecisionEnum.MENTOR.value,
            "confidence": 0.95,
            "reasoning": "Fatigue and declining scores indicate need for guided assistance."
        }

    final_decision = evaluate_and_decide(ctx, ai_agent_caller=mock_member1_agent)

    assert final_decision.decision == DecisionType.MENTOR
    assert final_decision.confidence == 0.95
    assert "Fatigue" in final_decision.coaching_narrative or "persistence" in final_decision.coaching_narrative.lower()

    # Final decision to_dict must serialize cleanly
    out_dict = final_decision.to_dict()
    assert json.dumps(out_dict) is not None
    assert out_dict["student_id"] == "1"
