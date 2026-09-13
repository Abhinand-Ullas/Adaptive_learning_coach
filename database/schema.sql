-- Database schema for Adaptive Learning Coach

-- Main student table storing current states and metrics
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    current_course TEXT,
    current_module TEXT,
    test_score REAL,
    previous_score REAL,
    assignment_score REAL,
    attempts INTEGER,
    streak_days INTEGER,
    difficulty_tier TEXT,
    tags TEXT,
    last_decision TEXT,
    reasoning TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Optional table to track historical agent decisions and quiz attempts for auditing
CREATE TABLE IF NOT EXISTS student_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    test_score REAL,
    assignment_score REAL,
    decision TEXT,
    reasoning TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);