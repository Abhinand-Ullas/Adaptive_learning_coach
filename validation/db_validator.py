import sqlite3

def validate_student_exists(cursor: sqlite3.Cursor, student_id: str) -> bool:
    """
    Checks if a student record exists in the database to satisfy foreign key constraints.
    """
    cursor.execute("SELECT 1 FROM students WHERE student_id = ?", (str(student_id),))
    return cursor.fetchone() is not None

def validate_attempt_record(cursor: sqlite3.Cursor, cleaned_data: dict) -> tuple[bool, str]:
    """
    Validates transactional integrity before running SQL inserts.
    """
    student_id = cleaned_data.get("student_id")
    
    if not validate_student_exists(cursor, student_id):
        return False, f"Foreign Key Error: Student ID '{student_id}' does not exist."
        
    score = cleaned_data.get("score", -1)
    if not (0.0 <= score <= 100.0):
        return False, "Integrity Error: Score out of valid range."
        
    return True, "Passed"