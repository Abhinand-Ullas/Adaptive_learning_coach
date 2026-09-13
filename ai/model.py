import os
from google import genai # pyrefly: ignore [missing-import]

def get_gemini_client() -> genai.Client:
    """
    Initializes and returns the Gemini API client.
    Requires GEMINI_API_KEY to be set in the environment variables.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Critical Error: GEMINI_API_KEY environment variable is missing.")
    
    # Initialize the new google-genai SDK client
    client = genai.Client(api_key=api_key)
    return client

def get_default_model_name() -> str:
    """Returns the default model to use for the agent."""
    # gemini-flash-latest is the active production flash tier
    return os.getenv("GEMINI_MODEL", "gemini-flash-latest")

def get_model_fallbacks() -> list:
    """Returns ordered candidate models for automatic failover during spikes in demand."""
    preferred = get_default_model_name()
    candidates = [preferred, "gemini-flash-latest", "gemini-3.5-flash", "gemini-3.6-flash"]
    return list(dict.fromkeys(candidates))



