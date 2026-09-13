-- Database schema for Adaptive Learning Coach (Normalized Relational Structure)

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    current_level TEXT DEFAULT 'BEGINNER' -- 'BEGINNER', 'INTERMEDIATE', 'ADVANCED'
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    difficulty TEXT NOT NULL,          -- 'BEGINNER', 'INTERMEDIATE', 'ADVANCED'
    score REAL NOT NULL,               -- e.g. 75.0
    time_spent_seconds INTEGER,        -- optional duration in seconds
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS quiz_question_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    subtopic TEXT NOT NULL,            -- e.g. 'Return Values', 'Default Parameters'
    is_correct BOOLEAN NOT NULL,       -- 1 = correct, 0 = incorrect
    error_tag TEXT,                    -- optional, e.g. 'TYPE_ERROR', 'OFF_BY_ONE'
    FOREIGN KEY (attempt_id) REFERENCES quiz_attempts(attempt_id)
);