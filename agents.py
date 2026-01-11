"""
Agent creation for the Health Assistant application.
Supports automatic API key rotation on rate limit errors.
"""

import os
from langchain_google_genai import ChatGoogleGenerativeAI

from config import api_key_manager, MODEL_NAME, MODEL_TEMPERATURE
from utils import create_agent
from prompts import (
    INTENT_ROUTER_PROMPT,
    INTAKE_AGENT_PROMPT,
    SYMPTOM_ANALYZER_PROMPT,
    DRUG_EXPLAINER_PROMPT,
    FOOD_INTAKE_PROMPT,
    FOOD_ANALYZER_PROMPT,
    HEALTH_IMPACT_PROMPT
)


def get_llm():
    """Get LLM instance with current available API key."""
    api_key = api_key_manager.get_available_key()
    if api_key:
        os.environ['GOOGLE_API_KEY'] = api_key
    return ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=MODEL_TEMPERATURE)


def refresh_llm():
    """Refresh the LLM with a new API key (called after rate limit)."""
    global llm
    api_key_manager.rotate_key()
    llm = get_llm()
    _recreate_agents()
    return llm


def _recreate_agents():
    """Recreate all agents with the new LLM."""
    global intent_router_agent, intake_agent, symptom_agent, explainer_agent
    global food_intake_agent, food_analyzer_agent, health_impact_agent
    
    intent_router_agent = create_agent(system_prompt=INTENT_ROUTER_PROMPT, llm=llm)
    intake_agent = create_agent(system_prompt=INTAKE_AGENT_PROMPT, llm=llm)
    symptom_agent = create_agent(system_prompt=SYMPTOM_ANALYZER_PROMPT, llm=llm)
    explainer_agent = create_agent(system_prompt=DRUG_EXPLAINER_PROMPT, llm=llm)
    food_intake_agent = create_agent(system_prompt=FOOD_INTAKE_PROMPT, llm=llm)
    food_analyzer_agent = create_agent(system_prompt=FOOD_ANALYZER_PROMPT, llm=llm)
    health_impact_agent = create_agent(system_prompt=HEALTH_IMPACT_PROMPT, llm=llm)


# Initialize LLM with first available key
llm = get_llm()

# ============================================================================
# CREATE ALL AGENTS
# ============================================================================

# Intent Router
intent_router_agent = create_agent(system_prompt=INTENT_ROUTER_PROMPT, llm=llm)

# Medical Agents
intake_agent = create_agent(system_prompt=INTAKE_AGENT_PROMPT, llm=llm)
symptom_agent = create_agent(system_prompt=SYMPTOM_ANALYZER_PROMPT, llm=llm)
explainer_agent = create_agent(system_prompt=DRUG_EXPLAINER_PROMPT, llm=llm)

# Food Analysis Agents
food_intake_agent = create_agent(system_prompt=FOOD_INTAKE_PROMPT, llm=llm)
food_analyzer_agent = create_agent(system_prompt=FOOD_ANALYZER_PROMPT, llm=llm)
health_impact_agent = create_agent(system_prompt=HEALTH_IMPACT_PROMPT, llm=llm)
