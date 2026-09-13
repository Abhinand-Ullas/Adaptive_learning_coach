"""
Enumerations for Learning Intelligence & Decision Engine.

Defines the standard vocabulary for learner classification, difficulty tiers,
performance trends, pedagogical strategies, and diagnostic reason codes.
"""

from enum import Enum


class DecisionType(str, Enum):
    """Primary pedagogical decisions produced by the learning engine."""
    REINFORCE = "REINFORCE"  # Target practice / remediation on knowledge gaps
    MENTOR = "MENTOR"        # Conceptual explanations, scaffolding, hints, or fatigue intervention
    ADVANCE = "ADVANCE"      # Progression to higher difficulty or next curricular topic


class DifficultyLevel(str, Enum):
    """Curriculum difficulty tiers."""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class ScoreTrend(str, Enum):
    """Categorical performance trajectory over recent quiz attempts."""
    IMPROVING = "IMPROVING"  # Score delta > +5%
    STABLE = "STABLE"        # Score delta within [-5%, +5%]
    DECLINING = "DECLINING"  # Score delta < -5%


class SubStrategy(str, Enum):
    """
    Granular pedagogical action associated with each DecisionType.
    Informs Member 1's prompting and Member 4's action execution.
    """
    # Strategies under REINFORCE
    TARGETED_DRILL = "TARGETED_DRILL"              # Practice questions focused on weak subtopics
    DIFFICULTY_DOWNGRADE = "DIFFICULTY_DOWNGRADE"  # Lowering question difficulty to rebuild confidence
    PREREQUISITE_REVIEW = "PREREQUISITE_REVIEW"    # Stepping back to review prerequisite foundational concepts

    # Strategies under MENTOR
    CONCEPTUAL_EXPLANATION = "CONCEPTUAL_EXPLANATION"  # Detailed breakdown of core concepts
    HINT_SCAFFOLDING = "HINT_SCAFFOLDING"              # Socratic hints and step-by-step guidance
    WORKED_EXAMPLE = "WORKED_EXAMPLE"                  # Fully solved analogous problem walkthrough
    FATIGUE_INTERVENTION = "FATIGUE_INTERVENTION"      # Encouragement and break suggestion after repeated attempts

    # Strategies under ADVANCE
    DIFFICULTY_UPGRADE = "DIFFICULTY_UPGRADE"          # Level up difficulty within the same module
    NEXT_TOPIC_UNLOCK = "NEXT_TOPIC_UNLOCK"            # Move to the next curricular module
    ACCELERATED_CHALLENGE = "ACCELERATED_CHALLENGE"    # Optional stretch/honor problems for high mastery (>95%)


class ReasonCode(str, Enum):
    """Machine-readable diagnostic reason codes justifying the engine's assessment."""
    MASTERY_ACHIEVED = "MASTERY_ACHIEVED"          # High scores across attempts (>=80%)
    LOW_RECENT_SCORE = "LOW_RECENT_SCORE"          # Most recent score failed threshold (<60%)
    DECLINING_TREND = "DECLINING_TREND"            # Recent scores are trending downward
    PERSISTENT_STRUGGLE = "PERSISTENT_STRUGGLE"    # Low scores across multiple attempts
    FATIGUE_DETECTED = "FATIGUE_DETECTED"          # 3+ consecutive failures, loop breaker needed
    ISOLATED_ANOMALY = "ISOLATED_ANOMALY"          # Single bad score with strong historical record
    HIGH_SCORE_VOLATILITY = "HIGH_SCORE_VOLATILITY"# Erratic swings between attempts
    COLD_START = "COLD_START"                      # First attempt on a topic, limited history
    TOPIC_DEFICIT = "TOPIC_DEFICIT"                # Identified subtopic with score <65%
