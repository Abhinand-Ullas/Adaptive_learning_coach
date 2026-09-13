"""
AI Agent Contracts and Safety Guardrails.

Manages data packaging for Member 1 (Gemini Agent) and validates returned AI decisions
against deterministic pedagogical boundaries to prevent hallucinations.
"""

import logging
from typing import Dict, Any, Tuple, Optional
from .enums import DecisionType, SubStrategy, ReasonCode
from .models import LearningAssessment
from .recommendations import generate_fallback_coaching_narrative

logger = logging.getLogger(__name__)


def build_agent_prompt_context(assessment: LearningAssessment) -> Dict[str, Any]:
    """
    Step 2: Packages LearningAssessment into a clean Python dictionary for Member 1.
    Member 1 injects these keys directly into the Gemini prompt template.
    """
    return assessment.to_agent_payload()


def validate_and_guardrail_ai_decision(
    assessment: LearningAssessment,
    ai_response: Optional[Dict[str, Any]]
) -> Tuple[DecisionType, SubStrategy, float, str, bool]:
    """
    Step 7: Safety Guardrail.
    Inspects Member 1's Gemini JSON response against deterministic boundaries.
    
    If Gemini hallucinates (e.g. returns ADVANCE when student scored 20% or failed 3 times),
    this guardrail overrides the AI decision and enforces the deterministic baseline.
    
    Returns:
        (approved_decision, approved_strategy, confidence, coaching_narrative, was_overridden)
    """
    fallback_narrative = generate_fallback_coaching_narrative(assessment)

    # If AI call failed, returned None, or malformed dict -> deterministic fallback
    if not ai_response or not isinstance(ai_response, dict):
        logger.warning(
            f"AI response is empty or invalid for student {assessment.learner_id}. Using deterministic fallback."
        )
        return (
            assessment.baseline_decision,
            assessment.primary_strategy,
            assessment.confidence,
            fallback_narrative,
            True,
        )

    raw_decision = str(ai_response.get("decision", "")).strip().upper()

    # Parse DecisionType enum
    try:
        proposed_decision = DecisionType(raw_decision)
    except ValueError:
        logger.warning(
            f"Unknown AI decision '{raw_decision}' for student {assessment.learner_id}. "
            f"Falling back to baseline {assessment.baseline_decision.value}."
        )
        return (
            assessment.baseline_decision,
            assessment.primary_strategy,
            assessment.confidence,
            fallback_narrative,
            True,
        )

    # ------------------------------------------------------------------
    # GUARDRAIL 1: Bounded Decision Enforcement
    # Gemini must choose from assessment.allowed_decisions
    # ------------------------------------------------------------------
    if proposed_decision not in assessment.allowed_decisions:
        logger.warning(
            f"GUARDRAIL TRIGGERED: Gemini proposed '{proposed_decision.value}', but allowed decisions "
            f"are {[d.value for d in assessment.allowed_decisions]}. Overriding to baseline '{assessment.baseline_decision.value}'."
        )
        return (
            assessment.baseline_decision,
            assessment.primary_strategy,
            assessment.confidence,
            fallback_narrative,
            True,
        )

    # ------------------------------------------------------------------
    # GUARDRAIL 2: Hard Absolute Safety Check
    # Even if prompted loosely, NEVER allow ADVANCE if consecutive failures >= 3 or mastery < 50%
    # ------------------------------------------------------------------
    if (
        proposed_decision == DecisionType.ADVANCE
        and (assessment.metrics.consecutive_failures >= 3 or assessment.metrics.mastery_score < 50.0)
    ):
        logger.warning(
            f"GUARDRAIL TRIGGERED: Rejecting ADVANCE for student {assessment.learner_id} due to low mastery "
            f"({assessment.metrics.mastery_score}%) or 3+ failures. Overriding to {assessment.baseline_decision.value}."
        )
        return (
            assessment.baseline_decision,
            assessment.primary_strategy,
            assessment.confidence,
            fallback_narrative,
            True,
        )

    # Parse or preserve SubStrategy
    raw_strategy = str(
        ai_response.get("selected_strategy") or ai_response.get("strategy", "")
    ).strip().upper()
    try:
        approved_strategy = SubStrategy(raw_strategy)
    except ValueError:
        approved_strategy = assessment.primary_strategy

    # Parse confidence
    try:
        conf = float(ai_response.get("confidence", assessment.confidence))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = assessment.confidence

    # Extract coaching narrative (supports Member 1 schemas: reasoning, behavioral_analysis)
    coaching_narrative = (
        ai_response.get("coaching_narrative")
        or ai_response.get("reasoning")
        or ai_response.get("behavioral_analysis")
        or ai_response.get("reason")
        or fallback_narrative
    )

    return (
        proposed_decision,
        approved_strategy,
        round(conf, 2),
        str(coaching_narrative).strip(),
        False,
    )
