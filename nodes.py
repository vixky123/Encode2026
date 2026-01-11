"""
Node functions for the Health Assistant LangGraph.
Includes automatic API key rotation on rate limit errors.
"""

import time
from typing import Literal
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from config import (
    API_DELAY, 
    FOOD_KEYWORDS, 
    MEDICAL_KEYWORDS, 
    MEDICAL_COMMANDS,
    FOOD_INDICATORS,
    api_key_manager
)
from state import HealthAssistantState
from utils import create_message_with_image, create_message_with_image_bytes
import agents  # Import module to allow refreshing


def invoke_with_retry(agent, messages_dict, max_retries=3):
    """
    Invoke an agent with automatic retry on rate limit errors.
    Rotates API keys when rate limits are hit.
    """
    for attempt in range(max_retries):
        try:
            return agent.invoke(messages_dict)
        except Exception as e:
            error_str = str(e).lower()
            # Check for rate limit errors
            if "429" in str(e) or "resource_exhausted" in error_str or "rate" in error_str:
                print(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries})")
                api_key_manager.mark_rate_limited()
                agents.refresh_llm()  # Refresh LLM with new key
                time.sleep(2)  # Brief pause before retry
            else:
                raise e
    # If all retries failed, raise the last error
    raise Exception("All API keys exhausted or rate limited. Please try again later.")


# ============================================================================
# KEYWORD-BASED INTENT NODE (Simple keyword matching - no LLM needed)
# ============================================================================

def keyword_intent_node(state: HealthAssistantState) -> dict:
    """
    Simple keyword-based routing:
    - If user_intent is already set (from execution cell), use it directly
    - Otherwise, do keyword matching on user_input
    """
    # Check if intent was already determined by the execution cell
    existing_intent = state.get("user_intent", "")
    if existing_intent in ["FOOD", "MEDICAL"]:
        # Intent already set, no need to re-detect
        return {"user_intent": existing_intent}
    
    user_input = state.get("user_input", "").lower().strip()
    
    # Check for food analysis keywords
    for keyword in FOOD_KEYWORDS:
        if keyword in user_input:
            return {"user_intent": "FOOD"}
    
    # Check for medical/health help keywords
    for keyword in MEDICAL_KEYWORDS:
        if keyword in user_input:
            return {"user_intent": "MEDICAL"}
    
    # Default: treat as unclear - will ask for clarification
    return {"user_intent": "UNCLEAR"}


# ============================================================================
# GET QUERY NODES - Ask for actual query after intent is determined
# ============================================================================

def get_food_query_node(state: HealthAssistantState) -> dict:
    """Asks user for the food/ingredient they want to analyze"""
    has_image = state.get("has_image", False)
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    existing_query = state.get("food_query", "")
    
    # If we already have a food query from the execution cell, use it
    if existing_query and existing_query not in ["", "Analyze the food label in the attached image"]:
        return {"food_query": existing_query}
    
    # If only image is provided, proceed directly
    if has_image and (image_path or image_bytes):
        return {"food_query": "Analyze the food label in the attached image"}
    
    # Otherwise, ask for the food query
    question = "What food or ingredient would you like me to analyze?\n\nYou can enter:\n• A single ingredient (e.g., 'turmeric', 'MSG')\n• A product name (e.g., 'Coca-Cola', 'Oreos')\n• An ingredient list (e.g., 'sugar, palm oil, sodium benzoate')"
    
    food_query = interrupt({
        "question": question,
        "intent": "FOOD",
        "prompt": f"🍎 Agent: {question}"
    })
    
    return {"food_query": food_query, "user_input": food_query}


def get_medical_query_node(state: HealthAssistantState) -> dict:
    """Asks user for their symptoms/medical concern"""
    has_image = state.get("has_image", False)
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    original_input = state.get("user_input", "")
    
    # Check if user already provided symptoms (not just command keywords)
    if original_input.lower().strip() not in MEDICAL_COMMANDS and len(original_input) > 10:
        # User already provided symptoms (longer text), proceed
        return {}
    
    # If image is provided with just the command, proceed
    if has_image and (image_path or image_bytes):
        return {"user_input": "Please analyze the symptoms shown in the attached image"}
    
    # Otherwise, ask for symptoms
    question = "Please describe your symptoms or health concern.\n\nFor example:\n• 'I have a headache and fever since morning'\n• 'What is paracetamol used for?'\n• 'I feel dizzy and my throat hurts'"
    
    symptoms = interrupt({
        "question": question,
        "intent": "MEDICAL",
        "prompt": f"🤖 Agent: {question}"
    })
    
    return {"user_input": symptoms}


def ask_intent_node(state: HealthAssistantState) -> dict:
    """Asks user to clarify their intent when unclear"""
    question = "What would you like help with?\n\n• Type 'FOOD ANALYSIS' to analyze food ingredients\n• Type 'HEALTH HELP' for medical consultation"
    
    intent_response = interrupt({
        "question": question,
        "intent": "UNCLEAR",
        "prompt": f"🤖 Agent: {question}"
    })
    
    # Parse the response
    response_lower = intent_response.lower().strip()
    if "food" in response_lower:
        return {"user_intent": "FOOD", "user_input": intent_response}
    elif "health" in response_lower or "medical" in response_lower:
        return {"user_intent": "MEDICAL", "user_input": intent_response}
    else:
        # Treat whatever they typed as the actual query - try to classify
        # If it looks like food, go food; otherwise medical
        if any(ind in response_lower for ind in FOOD_INDICATORS):
            return {"user_intent": "FOOD", "user_input": intent_response, "food_query": intent_response}
        else:
            return {"user_intent": "MEDICAL", "user_input": intent_response}


# ============================================================================
# MEDICAL NODES
# ============================================================================

def _get_message_with_image(text: str, state: HealthAssistantState) -> HumanMessage:
    """Helper to create message with image from state"""
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    
    if image_path:
        return create_message_with_image(text, image_path)
    elif image_bytes:
        return create_message_with_image_bytes(text, image_bytes)
    else:
        return HumanMessage(content=text)


def intake_node(state: HealthAssistantState) -> dict:
    """Evaluates patient info and decides if more questions needed"""
    conversation = state.get("conversation_history", "")
    user_input = state.get("user_input", "")
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    has_image = state.get("has_image", False)
    
    # If image is provided, skip follow-ups and go directly to diagnosis
    if has_image and (image_path or image_bytes):
        full_context = f"Patient's complaint with image: {user_input}\n\nPlease analyze the attached image along with the symptoms described and provide a diagnosis."
        message = _get_message_with_image(full_context, state)
        
        time.sleep(API_DELAY)  # Rate limit protection
        result = invoke_with_retry(agents.intake_agent, {"messages": [message]})
        response = result.content
        
        if "STATUS: EMERGENCY" in response:
            emergency_msg = response.split("MESSAGE:")[-1].strip() if "MESSAGE:" in response else response
            return {
                "is_emergency": True,
                "emergency_message": emergency_msg,
                "is_ready": False,
                "messages": [result]
            }
        
        summary = f"Patient complaint: {user_input}\n[Image analysis included - visual symptoms observed from attached image]"
        return {
            "patient_summary": summary,
            "is_ready": True,
            "is_emergency": False,
            "current_question": "",
            "messages": [result]
        }
    
    # Normal text-only flow with follow-up questions
    if conversation:
        full_context = f"Initial complaint: {user_input}\n\nConversation so far:\n{conversation}"
    else:
        full_context = f"Patient's complaint: {user_input}"
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.intake_agent, {"messages": [HumanMessage(content=full_context)]})
    response = result.content
    
    if "STATUS: EMERGENCY" in response:
        emergency_msg = response.split("MESSAGE:")[-1].strip() if "MESSAGE:" in response else response
        return {
            "is_emergency": True,
            "emergency_message": emergency_msg,
            "is_ready": False,
            "current_question": "",
            "messages": [result]
        }
    elif "STATUS: READY_FOR_DIAGNOSIS" in response:
        summary = response.split("SUMMARY:")[-1].strip() if "SUMMARY:" in response else response
        return {
            "patient_summary": summary,
            "is_ready": True,
            "is_emergency": False,
            "current_question": "",
            "messages": [result]
        }
    else:
        question = response.split("QUESTION:")[-1].strip() if "QUESTION:" in response else response
        return {
            "current_question": question,
            "is_ready": False,
            "is_emergency": False,
            "messages": [result]
        }


def medical_human_input_node(state: HealthAssistantState) -> dict:
    """Asks the human for medical follow-up input using LangGraph interrupt"""
    question = state.get("current_question", "")
    conversation = state.get("conversation_history", "")
    
    # Interrupt and wait for human input
    human_answer = interrupt({
        "question": question,
        "intent": "MEDICAL",
        "prompt": f"🤖 Agent:\n{question}\n\n👤 Please provide your answer:"
    })
    
    # Update conversation history with Q&A
    new_conversation = conversation + f"\nQ: {question}\nA: {human_answer}\n"
    
    return {
        "conversation_history": new_conversation,
        "current_question": ""
    }


def symptom_analyzer_node(state: HealthAssistantState) -> dict:
    """Analyzes symptoms and recommends drugs"""
    patient_summary = state["patient_summary"]
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    has_image = state.get("has_image", False)
    
    if has_image and (image_path or image_bytes):
        message = _get_message_with_image(
            f"Analyze these symptoms and the attached image, then recommend appropriate medications:\n\n{patient_summary}",
            state
        )
    else:
        message = HumanMessage(content=patient_summary)
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.symptom_agent, {"messages": [message]})
    
    return {
        "symptom_analysis": result.content,
        "messages": [result]
    }


def drug_explainer_node(state: HealthAssistantState) -> dict:
    """Explains the drug recommendations"""
    symptom_analysis = state["symptom_analysis"]
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.explainer_agent, {
        "messages": [HumanMessage(content=f"Drug recommendations:\n\n{symptom_analysis}")]
    })
    
    return {
        "final_explanation": result.content,
        "messages": [result]
    }


# ============================================================================
# FOOD ANALYSIS NODES
# ============================================================================

def food_intake_node(state: HealthAssistantState) -> dict:
    """Extracts food/ingredient information - processes the actual food query"""
    food_query = state.get("food_query", "") or state.get("user_input", "")
    image_path = state.get("image_path", "")
    image_bytes = state.get("image_bytes", b"")
    has_image = state.get("has_image", False)
    
    # Determine input mode and create appropriate message
    if has_image and (image_path or image_bytes):
        if food_query and food_query.lower() not in ["analyze the food label in the attached image", ""]:
            # Image + Text
            context = f"INPUT MODE: Image with text context\n\nUser's question/context: {food_query}\n\n[Food label/product image attached. Extract ingredients and address user's concerns.]"
        else:
            # Image Only
            context = "INPUT MODE: Image only\n\n[Food label/product image attached. Extract all visible ingredients, nutrition facts, allergens.]"
        message = _get_message_with_image(context, state)
    else:
        # Text Only
        context = f"INPUT MODE: Text only\n\nUser's food query: {food_query}\n\n[Analyze this food/ingredient. Provide comprehensive information.]"
        message = HumanMessage(content=context)
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.food_intake_agent, {"messages": [message]})
    response = result.content
    
    # Extract food data - be more lenient, treat any response as valid
    if "EXTRACTED_DATA:" in response:
        food_data = response.split("EXTRACTED_DATA:")[-1].strip()
    else:
        # Use the full response as food data
        food_data = response
    
    return {
        "food_data": food_data,
        "messages": [result]
    }


def food_analyzer_node(state: HealthAssistantState) -> dict:
    """Analyzes ingredients for health effects"""
    food_data = state["food_data"]
    food_query = state.get("food_query", "")
    
    context = f"Food query: {food_query}\n\nExtracted data:\n{food_data}"
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.food_analyzer_agent, {
        "messages": [HumanMessage(content=context)]
    })
    
    return {
        "food_analysis": result.content,
        "messages": [result]
    }


def health_impact_node(state: HealthAssistantState) -> dict:
    """Explains health implications in simple terms"""
    food_analysis = state["food_analysis"]
    food_query = state.get("food_query", "")
    
    context = f"Original query: {food_query}\n\nFood analysis:\n{food_analysis}"
    
    time.sleep(API_DELAY)  # Rate limit protection
    result = invoke_with_retry(agents.health_impact_agent, {
        "messages": [HumanMessage(content=context)]
    })
    
    return {
        "health_impact": result.content,
        "messages": [result]
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_after_keyword_intent(state: HealthAssistantState) -> Literal["get_food_query", "get_medical_query", "ask_intent"]:
    """Route based on keyword detection"""
    intent = state.get("user_intent", "UNCLEAR")
    
    if intent == "FOOD":
        return "get_food_query"
    elif intent == "MEDICAL":
        return "get_medical_query"
    else:
        return "ask_intent"


def route_after_ask_intent(state: HealthAssistantState) -> Literal["get_food_query", "get_medical_query"]:
    """Route after user clarifies intent"""
    intent = state.get("user_intent", "MEDICAL")
    
    if intent == "FOOD":
        return "get_food_query"
    else:
        return "get_medical_query"


def route_after_intake(state: HealthAssistantState) -> Literal["medical_human_input", "symptom_analyzer", "__end__"]:
    """Route based on whether we have enough information or emergency detected"""
    if state.get("is_emergency", False):
        return "__end__"
    elif state.get("is_ready", False):
        return "symptom_analyzer"
    else:
        return "medical_human_input"
