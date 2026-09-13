"""
Full Team Cross-Module Pipeline Integration Tests.

Verifies end-to-end flow across all four members:
- Member 3 (Validation & DB Schema): clean_quiz_submission, validate_student_exists, validate_attempt_record
- Member 2 (Learning Intelligence): build_validated_learner_context, metrics, evaluation, guardrails
- Member 1 (AI Agent): build_user_prompt, schema validation, mock agent responses
- Member 4 (Database Mutations): record_quiz_attempt, apply_learning_decision, level mutations
"""

import os
import sqlite3
import pytest

from validation import (
    clean_quiz_submission,
    validate_student_exists,
    validate_attempt_record,
    build_validated_learner_context,
    build_learner_context_from_db,
)
from actions import (
    record_quiz_attempt,
    apply_learning_decision,
    get_student,
    update_student_level,
    get_next_level,
)
from ai.learning_intelligence import (
    DecisionType,
    DifficultyLevel,
    SubStrategy,
    ReasonCode,
    compute_performance_metrics,
    create_learning_assessment,
    evaluate_and_decide,
    evaluate_deterministic,
)
from ai.prompts import build_user_prompt
from ai.schemas import AIProposedDecision, LearningDecision as Member1DecisionEnum

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "../database/schema.sql")


@pytest.fixture
def test_db(tmp_path):
    """Creates an isolated temporary SQLite database with normalized schema."""
    db_file = str(tmp_path / "test_coach.db")
    conn = sqlite3.connect(db_file)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    # Insert a sample student
    conn.execute(
        "INSERT INTO students (student_id, name, current_level) VALUES (?, ?, ?)",
        ("101", "Kavya", "BEGINNER")
    )
    conn.commit()
    conn.close()
    return db_file


def test_full_pipeline_advance_lifecycle(test_db):
    """
    Full 4-member integration lifecycle for a student achieving mastery:
    1. Member 3: Cleans quiz submission (92% on Functions).
    2. Member 3 Adapter: Builds strongly typed LearnerContext from DB.
    3. Member 2: Evaluates metrics and assessment.
    4. Member 1: Builds prompt and evaluates agent decision.
    5. Member 2: Guardrails and verifies safety.
    6. Member 4: Records attempt in quiz_attempts.
    7. Member 4: Applies decision and advances student level in SQLite.
    """
    student_id = "101"
    topic = "Functions"

    # Step 1: Member 3 Input Validation
    cleaned = clean_quiz_submission(
        student_id=student_id,
        topic=topic,
        difficulty="BEGINNER",
        raw_score=92.0,
        time_spent=45
    )
    assert cleaned["score"] == 92.0
    assert cleaned["difficulty"] == "BEGINNER"

    # Step 2: Adapter Context Construction (Prior to saving current attempt)
    ctx = build_validated_learner_context(
        student_id=student_id,
        topic=topic,
        raw_score=92.0,
        time_spent=45,
        difficulty="BEGINNER",
        db_path=test_db
    )
    assert ctx.current_score == 92.0
    assert ctx.current_difficulty == DifficultyLevel.BEGINNER
    assert len(ctx.score_history) == 0 # First attempt on Functions

    # Step 3: Member 2 Assessment
    assessment = create_learning_assessment(ctx)
    assert assessment.baseline_decision == DecisionType.ADVANCE

    # Step 4: Member 1 Prompt Formatting
    learner_ctx, perf_metrics = assessment.to_member1_format(time_spent_seconds=45)
    prompt = build_user_prompt(learner_ctx, perf_metrics)
    assert "Student ID: 101" in prompt
    assert "Current Topic: Functions" in prompt

    # Step 5: Member 2 Decision Engine & Guardrail
    decision = evaluate_deterministic(ctx)
    assert decision.decision == DecisionType.ADVANCE

    # Step 6: Member 4 Record Attempt in SQLite
    attempt_info = record_quiz_attempt(
        student_id=cleaned["student_id"],
        topic=cleaned["topic"],
        difficulty=cleaned["difficulty"],
        score=cleaned["score"],
        time_spent_seconds=cleaned["time_spent_seconds"],
        db_path=test_db
    )
    assert attempt_info["attempt_id"] == 1

    # Step 7: Member 4 Database Mutation
    update_res = apply_learning_decision(decision, db_path=test_db)
    assert update_res["previous_level"] == "BEGINNER"
    assert update_res["new_level"] == "INTERMEDIATE"

    # Verify student record in SQLite
    student_after = get_student(student_id, db_path=test_db)
    assert student_after["current_level"] == "INTERMEDIATE"

    # Verify reading from DB directly via adapter
    ctx_from_db = build_learner_context_from_db(student_id, topic, db_path=test_db)
    assert ctx_from_db.current_score == 92.0
    assert ctx_from_db.attempt_count == 1


def test_consecutive_failures_fatigue_breaker_lifecycle(test_db):
    """
    Tests iterative quiz attempts across 3 consecutive failures:
    Attempt 1: 52% -> REINFORCE (level stays BEGINNER)
    Attempt 2: 48% -> REINFORCE (level stays BEGINNER)
    Attempt 3: 42% -> MENTOR (Fatigue Breaker triggers human intervention)
    """
    student_id = "101"
    topic = "Recursion"

    # --- Attempt 1: 52% ---
    ctx1 = build_validated_learner_context(student_id, topic, 52.0, 60, "BEGINNER", db_path=test_db)
    assert len(ctx1.score_history) == 0
    dec1 = evaluate_deterministic(ctx1)
    assert dec1.decision == DecisionType.REINFORCE
    record_quiz_attempt(student_id, topic, "BEGINNER", 52.0, 60, db_path=test_db)
    apply_learning_decision(dec1, db_path=test_db)

    # --- Attempt 2: 48% ---
    ctx2 = build_validated_learner_context(student_id, topic, 48.0, 70, "BEGINNER", db_path=test_db)
    assert ctx2.score_history == [52.0]
    dec2 = evaluate_deterministic(ctx2)
    assert dec2.decision == DecisionType.REINFORCE
    record_quiz_attempt(student_id, topic, "BEGINNER", 48.0, 70, db_path=test_db)
    apply_learning_decision(dec2, db_path=test_db)

    # --- Attempt 3: 42% ---
    ctx3 = build_validated_learner_context(student_id, topic, 42.0, 80, "BEGINNER", db_path=test_db)
    assert ctx3.score_history == [52.0, 48.0]
    dec3 = evaluate_deterministic(ctx3)
    
    # 3 consecutive failures must trigger MENTOR (Fatigue Breaker)
    assert dec3.decision == DecisionType.MENTOR
    assert dec3.strategy == SubStrategy.FATIGUE_INTERVENTION
    assert ReasonCode.FATIGUE_DETECTED in dec3.reason_codes

    record_quiz_attempt(student_id, topic, "BEGINNER", 42.0, 80, db_path=test_db)
    update_res = apply_learning_decision(dec3, db_path=test_db)
    assert update_res["decision"] == "mentor"
    assert update_res["action"] == "Refer the student to a human mentor"
    assert update_res["new_level"] == "BEGINNER"


def test_collision_foreign_key_protection(test_db):
    """
    Verifies that Member 3 and Member 4 reject attempts for non-existent students.
    """
    with pytest.raises(ValueError, match="Student ID '999' does not exist"):
        build_validated_learner_context(
            student_id="999",
            topic="Loops",
            raw_score=75.0,
            db_path=test_db
        )

    with pytest.raises(ValueError, match="Foreign Key Error"):
        record_quiz_attempt(
            student_id="999",
            topic="Loops",
            difficulty="BEGINNER",
            score=75.0,
            db_path=test_db
        )


def test_collision_fractional_score_normalization(test_db):
    """
    Member 3 converts fractional scores (e.g. 0.88 -> 88.0).
    Verifies this is preserved through the adapter and decision engine.
    """
    ctx = build_validated_learner_context(
        student_id="101",
        topic="Syntax",
        raw_score=0.88,  # Fractional score
        time_spent=30,
        db_path=test_db
    )
    assert ctx.current_score == 88.0
    dec = evaluate_deterministic(ctx)
    assert dec.decision == DecisionType.ADVANCE


def test_apply_learning_decision_polymorphic_signatures(test_db):
    """
    Verifies apply_learning_decision works with:
    1. Member 2 LearningDecision object
    2. DecisionType enum
    3. Raw string
    """
    # 1. Raw string
    res1 = apply_learning_decision("101", "advance", reasoning="Great job", db_path=test_db)
    assert res1["new_level"] == "INTERMEDIATE"

    # 2. DecisionType Enum
    res2 = apply_learning_decision("101", DecisionType.ADVANCE, reasoning="Advancing again", db_path=test_db)
    assert res2["new_level"] == "ADVANCED"

    # 3. LearningDecision object (already at ADVANCED, so level stays at ADVANCED ceiling)
    ctx = build_validated_learner_context("101", "OOP", 95.0, db_path=test_db)
    dec = evaluate_deterministic(ctx)
    res3 = apply_learning_decision(dec, db_path=test_db)
    assert res3["student_id"] == "101"
    assert res3["new_level"] == "ADVANCED"
