import sqlite3
import os
from typing import Optional, Union, Dict, Any

from validation.input_validator import clean_quiz_submission
from validation.db_validator import validate_attempt_record


# Path to the SQLite database
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "learning_coach.db"
)


# Learning levels
LEARNING_LEVELS = [
    "BEGINNER",
    "INTERMEDIATE",
    "ADVANCED"
]


# Decision -> Action
ACTION_MAP = {
    "reinforce": "Give more practice exercises",
    "advance": "Move to the next level",
    "mentor": "Refer the student to a human mentor"
}


def get_student(student_id: Union[str, int], db_path: Optional[str] = None):
    """
    Get the student's current level from the database.
    """
    target_db = db_path or DB_PATH
    conn = sqlite3.connect(target_db)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT student_id, name, current_level
            FROM students
            WHERE student_id = ?
            """,
            (str(student_id).strip(),)
        )

        student = cursor.fetchone()

        if student is None:
            return None

        return dict(student)

    finally:
        conn.close()


def get_next_level(current_level: str) -> str:
    """
    Get the next learning level.

    BEGINNER -> INTERMEDIATE
    INTERMEDIATE -> ADVANCED
    ADVANCED -> ADVANCED
    """
    current_level = current_level.upper().strip()

    if current_level not in LEARNING_LEVELS:
        raise ValueError(
            f"Invalid learning level: {current_level}"
        )

    current_index = LEARNING_LEVELS.index(current_level)

    if current_index < len(LEARNING_LEVELS) - 1:
        return LEARNING_LEVELS[current_index + 1]

    return current_level


def update_student_level(student_id: Union[str, int], new_level: str, db_path: Optional[str] = None):
    """
    Update the student's current level in the students table.
    """
    target_db = db_path or DB_PATH
    new_level = new_level.upper().strip()
    if new_level not in LEARNING_LEVELS:
        raise ValueError(f"Invalid learning level: {new_level}")

    conn = sqlite3.connect(target_db)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE students
            SET current_level = ?
            WHERE student_id = ?
            """,
            (new_level, str(student_id).strip())
        )

        if cursor.rowcount == 0:
            raise ValueError(
                f"Student '{student_id}' does not exist."
            )

        conn.commit()

    finally:
        conn.close()


def record_quiz_attempt(
    student_id: Union[str, int],
    topic: str,
    difficulty: str,
    score: float,
    time_spent_seconds: Optional[int] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Records a completed quiz attempt into the quiz_attempts table.
    Validates input and database integrity before running the SQL insert.
    """
    target_db = db_path or DB_PATH

    # 1. Clean and normalize through Member 3 validator
    cleaned = clean_quiz_submission(
        student_id=str(student_id),
        topic=topic,
        difficulty=difficulty,
        raw_score=score,
        time_spent=time_spent_seconds,
    )

    conn = sqlite3.connect(target_db)
    try:
        cursor = conn.cursor()

        # 2. Transactional validation via Member 3 db validator
        is_valid, err_msg = validate_attempt_record(cursor, cleaned)
        if not is_valid:
            raise ValueError(f"Quiz attempt validation failed: {err_msg}")

        # 3. Insert record into quiz_attempts
        cursor.execute(
            """
            INSERT INTO quiz_attempts (student_id, topic, difficulty, score, time_spent_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cleaned["student_id"],
                cleaned["topic"],
                cleaned["difficulty"],
                cleaned["score"],
                cleaned["time_spent_seconds"],
            )
        )
        conn.commit()
        attempt_id = cursor.lastrowid

        return {
            "attempt_id": attempt_id,
            "student_id": cleaned["student_id"],
            "topic": cleaned["topic"],
            "difficulty": cleaned["difficulty"],
            "score": cleaned["score"],
            "time_spent_seconds": cleaned["time_spent_seconds"],
        }
    finally:
        conn.close()


def apply_learning_decision(
    student_id: Union[str, int, Any],
    decision: Union[str, Any] = None,
    reasoning: str = "",
    target_difficulty: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply the AI decision to the student.
    Supports either direct arguments or Member 2's LearningDecision object.

    reinforce:
        Keep current level.
        Give more practice.

    advance:
        Move to the next level.
        Give next-level material.

    mentor:
        Keep current level.
        Refer to human mentor.
    """
    # Check if student_id is actually a LearningDecision object from Member 2
    if hasattr(student_id, "decision") and hasattr(student_id, "student_id"):
        ld_obj = student_id
        actual_student_id = str(ld_obj.student_id).strip()
        decision_val = ld_obj.decision.value if hasattr(ld_obj.decision, "value") else str(ld_obj.decision)
        reasoning = ld_obj.coaching_narrative or reasoning
        if hasattr(ld_obj, "target_difficulty"):
            target_difficulty = (
                ld_obj.target_difficulty.value
                if hasattr(ld_obj.target_difficulty, "value")
                else str(ld_obj.target_difficulty)
            )
    else:
        actual_student_id = str(student_id).strip()
        decision_val = decision.value if hasattr(decision, "value") else str(decision)

    # Clean the AI decision
    decision_clean = decision_val.lower().strip()

    # Check whether decision is valid
    if decision_clean not in ACTION_MAP:
        raise ValueError(
            f"Invalid decision '{decision_val}'. "
            "Expected: reinforce, advance, or mentor."
        )

    # Get student
    student = get_student(actual_student_id, db_path=db_path)

    if student is None:
        raise ValueError(
            f"Student '{actual_student_id}' does not exist."
        )

    # Current level
    current_level = student["current_level"].upper()

    # Decide new level
    if decision_clean == "advance":
        new_level = get_next_level(current_level)
    else:
        new_level = current_level


    # Update database if level changed
    if new_level != current_level:
        update_student_level(
            actual_student_id,
            new_level,
            db_path=db_path
        )

    # Get action to take
    action = ACTION_MAP[decision_clean]

    # Return result
    return {
        "student_id": actual_student_id,
        "student_name": student["name"],
        "previous_level": current_level,
        "new_level": new_level,
        "decision": decision_clean,
        "action": action,
        "reasoning": reasoning
    }