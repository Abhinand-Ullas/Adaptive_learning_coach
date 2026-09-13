import sqlite3
import os


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


def get_student(student_id):
    """
    Get the student's current level from the database.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT student_id, name, current_level
            FROM students
            WHERE student_id = ?
            """,
            (student_id,)
        )

        student = cursor.fetchone()

        if student is None:
            return None

        return dict(student)

    finally:
        conn.close()


def get_next_level(current_level):
    """
    Get the next learning level.

    BEGINNER -> INTERMEDIATE
    INTERMEDIATE -> ADVANCED
    ADVANCED -> ADVANCED
    """

    current_level = current_level.upper()

    if current_level not in LEARNING_LEVELS:
        raise ValueError(
            f"Invalid learning level: {current_level}"
        )

    current_index = LEARNING_LEVELS.index(current_level)

    if current_index < len(LEARNING_LEVELS) - 1:
        return LEARNING_LEVELS[current_index + 1]

    return current_level


def update_student_level(student_id, new_level):
    """
    Update the student's current level in the students table.
    """

    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE students
            SET current_level = ?
            WHERE student_id = ?
            """,
            (new_level, student_id)
        )

        if cursor.rowcount == 0:
            raise ValueError(
                f"Student '{student_id}' does not exist."
            )

        conn.commit()

    finally:
        conn.close()


def apply_learning_decision(student_id, decision, reasoning=""):
    """
    Apply the AI decision to the student.

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

    # Clean the AI decision
    decision = decision.lower().strip()

    # Check whether decision is valid
    if decision not in ACTION_MAP:
        raise ValueError(
            f"Invalid decision '{decision}'. "
            "Expected: reinforce, advance, or mentor."
        )

    # Get student
    student = get_student(student_id)

    if student is None:
        raise ValueError(
            f"Student '{student_id}' does not exist."
        )

    # Current level
    current_level = student["current_level"].upper()

    # Decide new level
    if decision == "advance":
        new_level = get_next_level(current_level)
    else:
        new_level = current_level

    # Update database if level changed
    if new_level != current_level:
        update_student_level(
            student_id,
            new_level
        )

    # Get action to take
    action = ACTION_MAP[decision]

    # Return result
    return {
        "student_id": student_id,
        "student_name": student["name"],
        "previous_level": current_level,
        "new_level": new_level,
        "decision": decision,
        "action": action,
        "reasoning": reasoning
    }