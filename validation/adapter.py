"""
Validation Adapter (Collision Remediation: Member 3 <-> Member 2).

Bridges Member 3's clean_quiz_submission() dictionary output and SQLite attempt history
into Member 2's strongly-typed LearnerContext model.
"""

import os
import sqlite3
from typing import Optional, List

from validation.input_validator import clean_quiz_submission
from validation.db_validator import validate_student_exists
from ai.learning_intelligence.enums import DifficultyLevel
from ai.learning_intelligence.models import LearnerContext

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "learning_coach.db"
)


def build_validated_learner_context(
    student_id: str,
    topic: str,
    raw_score: float,
    time_spent: Optional[int] = None,
    difficulty: Optional[str] = None,
    db_path: Optional[str] = None,
) -> LearnerContext:
    """
    Cleans incoming quiz data via Member 3's input validator, verifies student existence
    in SQLite, queries prior score history, and returns Member 2's LearnerContext.
    """
    db_file = db_path or DEFAULT_DB_PATH
    
    # 1. Member 3 input cleaning and normalization
    default_diff = difficulty or "BEGINNER"
    cleaned = clean_quiz_submission(
        student_id=str(student_id),
        topic=topic,
        difficulty=default_diff,
        raw_score=raw_score,
        time_spent=time_spent,
    )

    clean_sid = cleaned["student_id"]
    clean_topic = cleaned["topic"]
    clean_score = cleaned["score"]
    clean_time = cleaned["time_spent_seconds"]

    # 2. Query SQLite for student verification and past attempts
    score_history: List[float] = []
    level_from_db: Optional[str] = None

    if os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        try:
            cursor = conn.cursor()

            # Verify student exists (Member 3 DB check)
            if not validate_student_exists(cursor, clean_sid):
                raise ValueError(f"Student ID '{clean_sid}' does not exist in database.")

            # Get student's current registered level if difficulty wasn't explicitly supplied
            cursor.execute("SELECT current_level FROM students WHERE student_id = ?", (clean_sid,))
            row = cursor.fetchone()
            if row and row[0]:
                level_from_db = row[0]

            # Fetch chronological past attempt scores
            cursor.execute("""
                SELECT score
                FROM quiz_attempts
                WHERE student_id = ? AND topic = ?
                ORDER BY attempt_id ASC
            """, (clean_sid, clean_topic))
            past_attempts = cursor.fetchall()
            score_history = [float(p[0]) for p in past_attempts]

        finally:
            conn.close()

    # 3. Determine difficulty level enum
    chosen_diff_str = (
        cleaned["difficulty"]
        if difficulty is not None
        else (level_from_db or cleaned["difficulty"])
    ).upper()

    try:
        current_difficulty = DifficultyLevel(chosen_diff_str)
    except ValueError:
        current_difficulty = DifficultyLevel.BEGINNER

    # 4. Construct Member 2's LearnerContext
    return LearnerContext(
        student_id=clean_sid,
        current_topic=clean_topic,
        current_difficulty=current_difficulty,
        current_score=clean_score,
        score_history=score_history,
        attempt_count=len(score_history) + 1,
        time_spent_seconds=clean_time,
    )


def build_learner_context_from_db(
    student_id: str,
    topic: str,
    db_path: Optional[str] = None,
) -> LearnerContext:
    """
    Loads an existing student's attempts from SQLite: the most recent attempt is treated as
    current_score and previous attempts as score_history.
    """
    db_file = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        if not validate_student_exists(cursor, str(student_id)):
            raise ValueError(f"Student ID '{student_id}' does not exist in database.")

        cursor.execute("""
            SELECT score, difficulty, time_spent_seconds
            FROM quiz_attempts
            WHERE student_id = ? AND topic = ?
            ORDER BY attempt_id ASC
        """, (str(student_id), topic))
        rows = cursor.fetchall()
        if not rows:
            raise ValueError(f"No quiz records found for student '{student_id}' on topic '{topic}'.")

        latest_score, latest_diff, latest_time = rows[-1]
        past_scores = [float(r[0]) for r in rows[:-1]]

        try:
            diff_enum = DifficultyLevel(str(latest_diff).upper())
        except ValueError:
            diff_enum = DifficultyLevel.BEGINNER

        return LearnerContext(
            student_id=str(student_id),
            current_topic=topic,
            current_difficulty=diff_enum,
            current_score=float(latest_score),
            score_history=past_scores,
            attempt_count=len(rows),
            time_spent_seconds=latest_time,
        )
    finally:
        conn.close()
