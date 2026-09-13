"""
Pedagogical Recommendation Engine.

Maps learning assessments into concrete curricular actions, next topics/difficulties,
and structured action payloads for Member 4 and the SQLite database.
Also provides a template-based coaching narrative generator as a zero-crash fallback.
"""

from typing import List, Dict, Optional, Tuple, Any
from .enums import (
    DecisionType,
    DifficultyLevel,
    SubStrategy,
    ReasonCode,
)
from .models import LearningAssessment


# Default curriculum progression graph for Python learning
DEFAULT_CURRICULUM: List[str] = [
    "Python Basics",
    "Variables and Data Types",
    "Control Flow and Conditionals",
    "Loops and Iteration",
    "Functions and Scope",
    "Data Structures",
    "Object-Oriented Programming",
]


def get_next_difficulty(current: DifficultyLevel) -> DifficultyLevel:
    """Steps difficulty up: BEGINNER -> INTERMEDIATE -> ADVANCED."""
    if current == DifficultyLevel.BEGINNER:
        return DifficultyLevel.INTERMEDIATE
    elif current == DifficultyLevel.INTERMEDIATE:
        return DifficultyLevel.ADVANCED
    return DifficultyLevel.ADVANCED


def get_lower_difficulty(current: DifficultyLevel) -> DifficultyLevel:
    """Steps difficulty down: ADVANCED -> INTERMEDIATE -> BEGINNER."""
    if current == DifficultyLevel.ADVANCED:
        return DifficultyLevel.INTERMEDIATE
    elif current == DifficultyLevel.INTERMEDIATE:
        return DifficultyLevel.BEGINNER
    return DifficultyLevel.BEGINNER


def get_next_topic(
    current_topic: str,
    curriculum: Optional[List[str]] = None
) -> Optional[str]:
    """Finds the next topic in the curriculum sequence."""
    topics = curriculum or DEFAULT_CURRICULUM
    # Case-insensitive lookup
    lower_map = {t.lower(): t for t in topics}
    current_lower = current_topic.lower()

    topic_keys = list(lower_map.keys())
    if current_lower in topic_keys:
        idx = topic_keys.index(current_lower)
        if idx + 1 < len(topics):
            return topics[idx + 1]
    return None


def generate_action_recommendation(
    assessment: LearningAssessment,
    curriculum: Optional[List[str]] = None
) -> Tuple[str, DifficultyLevel, Dict[str, Any]]:
    """
    Translates a LearningAssessment into an actionable specification for Member 4:
    Returns (suggested_action, target_difficulty, action_payload).
    """
    decision = assessment.baseline_decision
    strategy = assessment.primary_strategy
    current_diff = assessment.current_difficulty
    topic = assessment.topic
    gaps = assessment.identified_gaps or [topic]

    if decision == DecisionType.REINFORCE:
        if strategy == SubStrategy.DIFFICULTY_DOWNGRADE:
            target_diff = get_lower_difficulty(current_diff)
            action_code = "DOWNGRADE_DIFFICULTY_AND_DRILL"
        else:
            target_diff = current_diff
            action_code = "ASSIGN_DRILL"

        payload = {
            "action": action_code,
            "focus_topics": gaps,
            "question_count": 3,
            "difficulty": target_diff.value,
            "remediation_strategy": strategy.value,
        }
        return action_code, target_diff, payload

    elif decision == DecisionType.MENTOR:
        target_diff = current_diff
        action_code = "START_MENTORING_SESSION"
        payload = {
            "action": action_code,
            "pedagogical_mode": strategy.value,
            "focus_topics": gaps,
            "difficulty": target_diff.value,
            "intervention_reasons": [r.value for r in assessment.reason_codes],
        }
        return action_code, target_diff, payload

    else:  # ADVANCE
        if strategy == SubStrategy.DIFFICULTY_UPGRADE:
            target_diff = get_next_difficulty(current_diff)
            next_topic = topic
            action_code = "UPGRADE_DIFFICULTY"
        elif strategy == SubStrategy.NEXT_TOPIC_UNLOCK:
            target_diff = DifficultyLevel.BEGINNER
            next_topic = get_next_topic(topic, curriculum) or topic
            action_code = "UNLOCK_NEXT_TOPIC"
        else:  # ACCELERATED_CHALLENGE
            target_diff = current_diff
            next_topic = topic
            action_code = "ASSIGN_CHALLENGE_PROBLEM"

        payload = {
            "action": action_code,
            "target_difficulty": target_diff.value,
            "next_topic": next_topic,
            "mastery_score": round(assessment.metrics.mastery_score, 1),
        }
        return action_code, target_diff, payload


def generate_fallback_coaching_narrative(assessment: LearningAssessment) -> str:
    """
    Deterministic template fallback generator.
    Used when Gemini API is offline or throws rate-limit errors.
    Guarantees the system never crashes or shows empty text to judges.
    """
    topic = assessment.topic
    mastery = assessment.metrics.mastery_score
    reasons = assessment.reason_codes
    gaps_text = ", ".join(assessment.identified_gaps) if assessment.identified_gaps else "the key concepts"

    # Specific scenarios
    if ReasonCode.FATIGUE_DETECTED in reasons:
        return (
            f"You've been putting in great persistence on '{topic}'! Taking multiple attempts in a row "
            f"can be tiring. Let's step back, take a short breather, and review a clear, step-by-step example together."
        )

    if ReasonCode.ISOLATED_ANOMALY in reasons:
        return (
            f"You have a consistently strong record on '{topic}'. A single lower score is totally normal "
            f"and happens to every programmer! Let's do a quick review of {gaps_text} before you tackle it again."
        )

    if assessment.baseline_decision == DecisionType.ADVANCE:
        if assessment.primary_strategy == SubStrategy.ACCELERATED_CHALLENGE:
            return (
                f"Phenomenal work on '{topic}'! You've reached an elite mastery score of {mastery}%. "
                f"We've unlocked an advanced challenge problem to stretch your skills even further."
            )
        return (
            f"Excellent job mastering '{topic}'! With a solid mastery score of {mastery}%, "
            f"you are ready to advance. Let's keep this strong momentum going!"
        )

    if assessment.baseline_decision == DecisionType.REINFORCE:
        return (
            f"Good effort on '{topic}'! We noticed a few areas that need extra practice ({gaps_text}). "
            f"We've prepared a focused 3-question drill to help you build confidence and lock in these concepts."
        )

    # General MENTOR
    return (
        f"You are making steady progress on '{topic}' with a {mastery}% mastery score. "
        f"Let's review a conceptual walkthrough and key hints to help push your comprehension to the next level."
    )
