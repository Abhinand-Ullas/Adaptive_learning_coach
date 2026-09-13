"""
Live test for ai.agent.get_learning_decision with automatic failover.
"""
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from ai.agent import get_learning_decision

def run_agent_test():
    learner_context = {
        "student_id": "1",
        "course_name": "Python",
        "current_topic": "CSS",
    }
    performance_metrics = {
        "recent_score_avg": 42.0,
        "trend": "declining",
        "attempts_on_current_topic": 3,
        "completion_percentage": 50,
        "time_spent_minutes": 1.0,
    }

    print("Invoking get_learning_decision()...")
    t0 = time.time()
    decision = get_learning_decision(learner_context, performance_metrics)
    elapsed = time.time() - t0

    print(f"Elapsed Time: {elapsed:.2f}s")
    print(f"Decision: {decision.get('decision')}")
    print(f"Confidence: {decision.get('confidence')}")
    print(f"Reasoning: {decision.get('reasoning')}")
    print(f"Behavioral Analysis: {decision.get('behavioral_analysis')}")

    # Check that fallback was NOT triggered
    is_fallback = "Fallback triggered" in decision.get("behavioral_analysis", "")
    if is_fallback:
        print("\n[ALERT] Fallback was triggered.")
    else:
        print("\n[SUCCESS] Live Gemini Agent response obtained successfully!")

if __name__ == "__main__":
    run_agent_test()
