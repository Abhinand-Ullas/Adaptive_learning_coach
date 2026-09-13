from enum import Enum
from pydantic import BaseModel, Field

class LearningDecision(str, Enum):
    REINFORCE = "REINFORCE"
    ADVANCE = "ADVANCE"
    MENTOR = "MENTOR"

class AIProposedDecision(BaseModel):
    """
    The exact structured JSON format the AI Agent must return.
    """
    behavioral_analysis: str = Field(
        description="A detailed analysis of the student's effort (time/attempts) versus their results (score), establishing their current learning state before making a decision."
    )
    decision: LearningDecision = Field(
        description="The recommended action to take based on the learner's state."
    )
    confidence: float = Field(
        description="A confidence score between 0.0 and 1.0 representing how certain the AI is.",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="A short, clear explanation of why this decision was chosen based on the metrics."
    )
