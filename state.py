"""
State definitions for the Health Assistant application.
"""

from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HealthAssistantState(TypedDict, total=False):
    """
    Unified state for both Medical and Food Analysis flows.
    Using total=False to allow optional fields.
    """
    # Common fields
    user_input: str                # The actual query (symptoms or food item)
    image_path: str                # Optional image path
    image_bytes: bytes             # Image bytes (for Gradio)
    has_image: bool                # Flag to indicate if image was provided
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Intent routing (set by keyword detection)
    user_intent: str               # "MEDICAL" or "FOOD"
    
    # Medical consultation fields
    conversation_history: str      # Accumulates all Q&A
    patient_summary: str           # Final summary when ready
    symptom_analysis: str
    final_explanation: str
    is_ready: bool                 # Flag to check if ready for diagnosis
    is_emergency: bool             # Flag for emergency situations
    emergency_message: str         # Emergency message to display
    current_question: str          # Current question being asked
    
    # Food analysis fields
    food_query: str                # The food/ingredient to analyze
    food_data: str                 # Extracted food/ingredient data
    food_analysis: str             # Detailed ingredient analysis
    health_impact: str             # Health impact explanation
