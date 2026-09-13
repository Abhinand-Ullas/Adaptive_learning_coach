import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '../data/learning_coach.db')

def seed_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables from schema.sql
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        cursor.executescript(f.read())

    # 1. Insert base student profiles matching the new schema
    mock_students = [
        ("1", "Anu", "BEGINNER"),
        ("2", "Rahul", "ADVANCED"),
        ("3", "Meera", "BEGINNER")
    ]
    cursor.executemany("""
        INSERT OR REPLACE INTO students (student_id, name, current_level) 
        VALUES (?, ?, ?)
    """, mock_students)

    # 2. Insert chronological quiz attempts to feed the agent's score_history
    mock_attempts = [
        ("1", "CSS", "BEGINNER", 60.0, 45),
        ("1", "CSS", "BEGINNER", 51.0, 50),
        ("1", "CSS", "BEGINNER", 42.0, 60),  # Latest attempt for Anu
        ("2", "JS", "ADVANCED", 91.0, 20),   # Latest attempt for Rahul
        ("3", "MERN stack", "BEGINNER", 48.0, 90) # Latest attempt for Meera
    ]
    cursor.executemany("""
        INSERT INTO quiz_attempts (student_id, topic, difficulty, score, time_spent_seconds) 
        VALUES (?, ?, ?, ?, ?)
    """, mock_attempts)

    conn.commit()
    conn.close()
    print("Database seeded successfully with normalized relational tables!")

if __name__ == "__main__":
    seed_database()