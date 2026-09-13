def clean_quiz_submission(student_id: str, topic: str, difficulty: str, raw_score: float, time_spent=None) -> dict:
    """
    Cleans, validates, and standardizes raw data coming from the quiz UI 
    before it is committed to SQLite or passed to the AI agent.
    """
    if not student_id or not str(student_id).strip():
        raise ValueError("Student ID cannot be empty.")
    if not topic or not str(topic).strip():
        raise ValueError("Topic cannot be empty.")
        
    # Handle fractional scores (e.g., 0.85 -> 85.0) vs percentages (85.0)
    if 0.0 <= raw_score <= 1.0:
        score = raw_score * 100.0
    else:
        score = float(raw_score)
        
    # Enforce strict score bounds
    if not (0.0 <= score <= 100.0):
        raise ValueError(f"Score {score} is out of bounds. Must be between 0.0 and 100.0.")
        
    # Standardize difficulty tier
    norm_difficulty = difficulty.strip().upper()
    if norm_difficulty not in ["BEGINNER", "INTERMEDIATE", "ADVANCED"]:
        norm_difficulty = "BEGINNER"
        
    # Validate time spent
    time_sec = int(time_spent) if time_spent is not None and int(time_spent) >= 0 else 0
    
    return {
        "student_id": str(student_id).strip(),
        "topic": topic.strip(),
        "difficulty": norm_difficulty,
        "score": score,
        "time_spent_seconds": time_sec
    }