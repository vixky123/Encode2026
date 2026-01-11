"""
LangGraph workflow builder for the Health Assistant application.
"""

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from state import HealthAssistantState
from nodes import (
    keyword_intent_node,
    ask_intent_node,
    get_food_query_node,
    get_medical_query_node,
    intake_node,
    medical_human_input_node,
    symptom_analyzer_node,
    drug_explainer_node,
    food_intake_node,
    food_analyzer_node,
    health_impact_node,
    route_after_keyword_intent,
    route_after_ask_intent,
    route_after_intake
)


def build_health_assistant_graph(checkpointer=None):
    """
    Build and compile the Health Assistant graph.
    
    Args:
        checkpointer: Optional checkpointer for state persistence (required for interrupts)
    
    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(HealthAssistantState)
    
    # ========================================================================
    # ADD ALL NODES
    # ========================================================================
    
    # Entry point - Keyword-based intent detection
    workflow.add_node("keyword_intent", keyword_intent_node)
    
    # Intent clarification node
    workflow.add_node("ask_intent", ask_intent_node)
    
    # Query collection nodes
    workflow.add_node("get_food_query", get_food_query_node)
    workflow.add_node("get_medical_query", get_medical_query_node)
    
    # Medical flow nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("medical_human_input", medical_human_input_node)
    workflow.add_node("symptom_analyzer", symptom_analyzer_node)
    workflow.add_node("drug_explainer", drug_explainer_node)
    
    # Food flow nodes (linear - no loops needed)
    workflow.add_node("food_intake", food_intake_node)
    workflow.add_node("food_analyzer", food_analyzer_node)
    workflow.add_node("health_impact", health_impact_node)
    
    # ========================================================================
    # DEFINE EDGES
    # ========================================================================
    
    # Entry point
    workflow.add_edge(START, "keyword_intent")
    
    # Keyword intent routing
    workflow.add_conditional_edges(
        "keyword_intent",
        route_after_keyword_intent,
        {
            "get_food_query": "get_food_query",
            "get_medical_query": "get_medical_query",
            "ask_intent": "ask_intent"
        }
    )
    
    # After asking intent, route to appropriate query node
    workflow.add_conditional_edges(
        "ask_intent",
        route_after_ask_intent,
        {
            "get_food_query": "get_food_query",
            "get_medical_query": "get_medical_query"
        }
    )
    
    # Food flow: LINEAR (no loops)
    # get_food_query → food_intake → food_analyzer → health_impact → END
    workflow.add_edge("get_food_query", "food_intake")
    workflow.add_edge("food_intake", "food_analyzer")
    workflow.add_edge("food_analyzer", "health_impact")
    workflow.add_edge("health_impact", END)
    
    # Medical flow: get_medical_query → intake → (loop or proceed)
    workflow.add_edge("get_medical_query", "intake")
    
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "medical_human_input": "medical_human_input",
            "symptom_analyzer": "symptom_analyzer",
            "__end__": END
        }
    )
    
    # Medical human input loops back to intake
    workflow.add_edge("medical_human_input", "intake")
    
    # Medical flow completion
    workflow.add_edge("symptom_analyzer", "drug_explainer")
    workflow.add_edge("drug_explainer", END)
    
    # ========================================================================
    # COMPILE
    # ========================================================================
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)


# Create default graph instance with memory checkpointer
memory = MemorySaver()
health_assistant_graph = build_health_assistant_graph(checkpointer=memory)
