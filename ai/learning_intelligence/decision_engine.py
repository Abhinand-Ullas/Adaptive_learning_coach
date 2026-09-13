"""
Decision Engine Master Orchestrator.

Ties together all 7 steps of the cross-team architecture:
1. Calculates performance metrics (metrics.py)
2. Builds baseline assessment & prompt context (evaluator.py & contracts.py)
3. Delegates to Member 1's Gemini agent (if supplied)
4. Enforces safety guardrails & fallback (contracts.py)
5. Packages final LearningDecision with actionable payload for Member 4 (models.py & recommendations.py)
"""

import logging
from typing import Optional, Callable, Dict, Any
from .models import LearnerContext, LearningDecision
from .evaluator import create_learning_assessment
from .contracts import build_agent_prompt_context, validate_and_guardrail_ai_decision
from .recommendations import generate_action_recommendation

logger = logging.getLogger(__name__)


def evaluate_and_decide(
    context: LearnerContext,
    ai_agent_caller: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
) -> LearningDecision:
    """
    Master pipeline executing the full 7-step architecture.
    
    Args:
        context: Validated LearnerContext from Member 3.
        ai_agent_caller: Optional callable from Member 1 that invokes Gemini API.
                         Takes the prompt context dict and returns Gemini's JSON dict.
                         If None or if it throws an exception, the system activates
                         the deterministic fallback seamlessly.
                         
    Returns:
        LearningDecision: Validated decision, target difficulty, coaching narrative,
                          and action payload ready for Member 4.
    """
    # Step 1 & 2: Calculate metrics, evaluate state, package assessment
    assessment = create_learning_assessment(context)
    prompt_context = build_agent_prompt_context(assessment)

    # Steps 3-6: Member 1 Gemini Execution (if provided)
    ai_response: Optional[Dict[str, Any]] = None
    if ai_agent_caller is not None:
        try:
            ai_response = ai_agent_caller(prompt_context)
        except Exception as exc:
            logger.error(f"Error calling Member 1 Gemini agent: {exc}. Switching to deterministic fallback.")
            ai_response = None

    # Step 7: Safety Guardrails & Fallback
    (
        final_decision,
        final_strategy,
        confidence,
        narrative,
        was_overridden,
    ) = validate_and_guardrail_ai_decision(assessment, ai_response)

    # Sync finalized decision and strategy onto assessment for action generation
    assessment.baseline_decision = final_decision
    assessment.primary_strategy = final_strategy

    # Generate action payload for Member 4
    suggested_action, target_diff, action_payload = generate_action_recommendation(assessment)

    return LearningDecision(
        student_id=context.student_id,
        decision=final_decision,
        strategy=final_strategy,
        topic=context.current_topic,
        target_difficulty=target_diff,
        confidence=confidence,
        reason_codes=assessment.reason_codes,
        coaching_narrative=narrative,
        suggested_action=suggested_action,
        action_payload=action_payload,
    )


def evaluate_deterministic(context: LearnerContext) -> LearningDecision:
    """
    Runs the pipeline purely deterministically without calling Gemini.
    Ideal for local offline testing, zero-latency execution, or quick demos.
    """
    return evaluate_and_decide(context, ai_agent_caller=None)
