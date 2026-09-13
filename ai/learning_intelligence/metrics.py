"""
Feature and Performance Metrics Engine for Learning Intelligence.

Translates raw quiz attempts and scores into quantitative signals:
- Exponential Moving Average (EWMA) mastery score
- Score trend and trajectory (IMPROVING, STABLE, DECLINING)
- Consecutive failure counter for fatigue detection
- Consistency index (standard deviation)
- Subtopic strengths and gaps identification
"""

import math
from typing import List, Dict, Tuple
from .enums import ScoreTrend
from .models import LearnerContext, PerformanceMetrics


def calculate_historical_average(scores: List[float]) -> float:
    """Calculates the unweighted arithmetic mean of scores."""
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 1)


def calculate_mastery_score(scores: List[float], alpha: float = 0.60) -> float:
    """
    Calculates Exponentially Weighted Moving Average (EWMA) of scores.
    Recent scores carry more weight (alpha=0.60), reflecting current true competence.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return round(scores[0], 1)

    ema = scores[0]
    for score in scores[1:]:
        ema = (alpha * score) + ((1.0 - alpha) * ema)

    # Clamp to [0.0, 100.0]
    ema = max(0.0, min(100.0, ema))
    return round(ema, 1)


def calculate_score_trend(
    scores: List[float],
    threshold: float = 5.0
) -> Tuple[ScoreTrend, float]:
    """
    Evaluates score trajectory.
    Compares latest score to the moving baseline of prior scores.
    Returns (ScoreTrend, score_delta).
    """
    if len(scores) < 2:
        return ScoreTrend.STABLE, 0.0

    current = scores[-1]
    # If 3 or more attempts, compare against the average of prior attempts for stability
    if len(scores) >= 3:
        prior_baseline = sum(scores[:-1]) / len(scores[:-1])
    else:
        prior_baseline = scores[-2]

    delta = current - prior_baseline

    if delta > threshold:
        trend = ScoreTrend.IMPROVING
    elif delta < -threshold:
        trend = ScoreTrend.DECLINING
    else:
        trend = ScoreTrend.STABLE

    return trend, round(delta, 1)


def calculate_consecutive_failures(
    scores: List[float],
    fail_threshold: float = 60.0
) -> int:
    """
    Counts consecutive attempts scoring strictly below fail_threshold (<60.0)
    starting from the most recent attempt backwards.
    """
    if not scores:
        return 0

    count = 0
    for score in reversed(scores):
        if score < fail_threshold:
            count += 1
        else:
            break
    return count


def calculate_consistency_index(scores: List[float]) -> float:
    """
    Calculates the population standard deviation across attempts.
    Lower value indicates consistent performance; higher value (>18) indicates volatility.
    """
    if len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = math.sqrt(variance)
    return round(std_dev, 1)


def extract_topic_strengths_and_gaps(
    topic_scores: Dict[str, float],
    weak_threshold: float = 65.0,
    strong_threshold: float = 80.0
) -> Tuple[List[str], List[str]]:
    """
    Categorizes subtopics into weak (<65%) and strong (>=80%).
    Returns (weak_topics, strong_topics).
    """
    weak_topics = [
        topic for topic, score in topic_scores.items() if score < weak_threshold
    ]
    strong_topics = [
        topic for topic, score in topic_scores.items() if score >= strong_threshold
    ]
    return sorted(weak_topics), sorted(strong_topics)


def compute_performance_metrics(context: LearnerContext) -> PerformanceMetrics:
    """
    Master metric extraction function for Step 1 of the intelligence engine.
    Takes a validated LearnerContext and returns a complete PerformanceMetrics object.
    """
    full_scores = context.full_score_sequence()
    is_cold_start = len(context.score_history) == 0

    hist_avg = calculate_historical_average(full_scores)
    mastery = calculate_mastery_score(full_scores)
    trend, delta = calculate_score_trend(full_scores)
    consec_fails = calculate_consecutive_failures(full_scores)
    consistency = calculate_consistency_index(full_scores)
    weak_topics, strong_topics = extract_topic_strengths_and_gaps(context.topic_scores)

    # Retain the last 5 scores for recent history tracking
    recent_history = full_scores[-5:]

    return PerformanceMetrics(
        historical_average=hist_avg,
        mastery_score=mastery,
        score_trend=trend,
        score_delta=delta,
        consecutive_failures=consec_fails,
        consistency_index=consistency,
        recent_scores=recent_history,
        weak_topics=weak_topics,
        strong_topics=strong_topics,
        is_cold_start=is_cold_start,
    )
