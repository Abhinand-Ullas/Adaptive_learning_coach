"""
Main AI Agent integration logic.
Responsible for gluing together context, prompts, and the Gemini model.
(Member 1 Responsibility)
"""

import json
from google.genai import types
from ai.model import get_gemini_client, get_default_model_name
from ai.prompts import COACH_SYSTEM_PROMPT, build_user_prompt
from ai.schemas import AIProposedDecision

def get_learning_decision(learner_context: dict, performance_metrics: dict) -> dict:
    """
    Takes validated student context, formats the prompt,
    calls the Gemini model, and returns a structured decision.
    """
    try:
        # 1. Initialize our secure client
        client = get_gemini_client()
        model_name = get_default_model_name()
        
        # 2. Build the exact text Gemini will read
        user_prompt = build_user_prompt(learner_context, performance_metrics)
        
        # 3. Call the API, forcing it to use our exact Pydantic schema
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=COACH_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=AIProposedDecision,
                temperature=0.2, # Low temperature so it makes logical, not creative, decisions
            ),
        )
        
        # 4. Convert the JSON text response back into a standard Python dictionary
        decision_dict = json.loads(response.text)
        return decision_dict
        
    except Exception as e:
        # 5. FALLBACK LOGIC: If the internet dies, the API goes down, or Gemini hallucinates
        print(f"AI Agent Warning: Failed to connect to Gemini or parse response. Error: {e}")
        
        # Safe default to ensure the application never crashes
        return {
            "behavioral_analysis": "Fallback triggered. Unable to analyze behavior due to system error.",
            "decision": "REINFORCE",
            "confidence": 0.0,
            "reasoning": "System fallback due to AI service disruption."
        }
