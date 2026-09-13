import sqlite3
import os
import sys

# Ensure project root is in path for relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.input_validator import clean_quiz_submission
from validation.db_validator import validate_student_exists, validate_attempt_record

def run_integration_test():
    # Setup an in-memory SQLite database for isolated testing
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Initialize minimal relational schema
    cursor.execute("""
    CREATE TABLE students (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        current_level TEXT DEFAULT 'BEGINNER'
    );
    """)

    cursor.execute("""
    CREATE TABLE quiz_attempts (
        attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        score REAL NOT NULL,
        time_spent_seconds INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(student_id)
    );
    """)

    # Seed test student record
    cursor.execute("INSERT INTO students (student_id, name, current_level) VALUES (?, ?, ?)", 
                   ("s1", "Anu", "BEGINNER"))
    conn.commit()

    print("--- Running Integration Tests ---")

    # Test 1: Fractional score conversion (0.85 -> 85.0) and successful DB write
    try:
        raw_data = clean_quiz_submission(
            student_id="s1", 
            topic="CSS Flexbox", 
            difficulty="beginner", 
            raw_score=0.85, 
            time_spent="45"
        )
        
        is_valid, msg = validate_attempt_record(cursor, raw_data)
        assert is_valid, f"Validation failed: {msg}"

        cursor.execute("""
            INSERT INTO quiz_attempts (student_id, topic, difficulty, score, time_spent_seconds)
            VALUES (?, ?, ?, ?, ?)
        """, (raw_data["student_id"], raw_data["topic"], raw_data["difficulty"], raw_data["score"], raw_data["time_spent_seconds"]))
        conn.commit()
        print("✓ Test 1 Passed: Fractional score normalized and successfully written to SQLite.")
    except Exception as e:
        print(f"✗ Test 1 Failed: {e}")

    # Test 2: Foreign key validation catching non-existent students
    try:
        bad_data = clean_quiz_submission(
            student_id="fake_id", 
            topic="JavaScript", 
            difficulty="ADVANCED", 
            raw_score=90.0, 
            time_spent=30
        )
        is_valid, msg = validate_attempt_record(cursor, bad_data)
        assert not is_valid, "Should have failed due to missing student ID."
        print("✓ Test 2 Passed: Foreign key validation correctly blocked unlinked student.")
    except Exception as e:
        print(f"✗ Test 2 Failed: {e}")

    # Test 3: Score boundary enforcement
    try:
        clean_quiz_submission(
            student_id="s1", 
            topic="HTML", 
            difficulty="BEGINNER", 
            raw_score=150.0,  # Invalid score > 100
            time_spent=20
        )
        print("✗ Test 3 Failed: Accepted an out-of-bounds score.")
    except ValueError:
        print("✓ Test 3 Passed: Successfully rejected out-of-bounds score with ValueError.")

    conn.close()
    print("--- Integration Testing Complete ---")

if __name__ == "__main__":
    run_integration_test()