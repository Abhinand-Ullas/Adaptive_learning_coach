"""
Main AI Agent integration logic.
Responsible for gluing together context, prompts, and the Gemini model.
(Member 1 Responsibility)
"""

import json
from google.genai import types
from ai.model import get_gemini_client, get_default_model_name, get_model_fallbacks
from ai.prompts import COACH_SYSTEM_PROMPT, build_user_prompt
from ai.schemas import AIProposedDecision

def get_learning_decision(learner_context: dict, performance_metrics: dict) -> dict:
    """
    Takes validated student context, formats the prompt,
    calls the Gemini model with automatic multi-model failover,
    and returns a structured decision.
    """
    try:
        # 1. Initialize our secure client
        client = get_gemini_client()
        candidate_models = get_model_fallbacks()
        
        # 2. Build the exact text Gemini will read
        user_prompt = build_user_prompt(learner_context, performance_metrics)
        
        last_error = None
        for model_name in candidate_models:
            try:
                # Call Gemini with structured schema
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=COACH_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=AIProposedDecision,
                        temperature=0.2,
                    ),
                )
                decision_dict = json.loads(response.text)
                return decision_dict
            except Exception as model_err:
                last_error = model_err
                continue

        # If all models exhausted:
        raise last_error or RuntimeError("All Gemini candidate models were unavailable.")
        
    except Exception as e:
        # Fallback logic if all models are unavailable
        print(f"AI Agent Warning: Failed to connect to Gemini or parse response. Error: {e}")
        
        # Safe default to ensure the application never crashes
        return {
            "behavioral_analysis": "Fallback triggered. Unable to analyze behavior due to system error.",
            "decision": "REINFORCE",
            "confidence": 0.0,
            "reasoning": "System fallback due to AI service disruption."
        }

