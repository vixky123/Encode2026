"""
Gradio interface for the Health Assistant application.
Supports both Medical Consultation and Food Analysis with image input.
"""

import gradio as gr
import time
import os
from pathlib import Path
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

# Import our modules
from graph import build_health_assistant_graph
from state import HealthAssistantState


# ============================================================================
# GLOBAL STATE MANAGEMENT
# ============================================================================

class SessionManager:
    """Manages multiple user sessions with their own graph instances."""
    
    def __init__(self):
        self.sessions = {}
    
    def get_session(self, session_id: str):
        """Get or create a session."""
        if session_id not in self.sessions:
            memory = MemorySaver()
            self.sessions[session_id] = {
                "graph": build_health_assistant_graph(checkpointer=memory),
                "config": {"configurable": {"thread_id": session_id}},
                "state": None,
                "intent": None,
                "awaiting_followup": False,
                "conversation": []
            }
        return self.sessions[session_id]
    
    def reset_session(self, session_id: str):
        """Reset a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        return self.get_session(session_id)


session_manager = SessionManager()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_image_bytes(image_path: str) -> bytes:
    """Read image file and return bytes."""
    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as f:
            return f.read()
    return b""


def format_chat_message(role: str, content: str) -> dict:
    """Format a message for Gradio chatbot."""
    return {"role": role, "content": content}


def create_initial_state(intent: str, query: str, image_path: str = None) -> dict:
    """Create the initial state for the graph."""
    has_image = bool(image_path and Path(image_path).exists())
    image_bytes = get_image_bytes(image_path) if has_image else b""
    
    state = {
        "user_input": query if query else ("Analyze the attached image" if has_image else ""),
        "image_path": image_path if has_image else "",
        "image_bytes": image_bytes,
        "has_image": has_image,
        "user_intent": intent,
        "conversation_history": "",
        "patient_summary": "",
        "symptom_analysis": "",
        "final_explanation": "",
        "is_ready": False,
        "is_emergency": False,
        "emergency_message": "",
        "current_question": "",
        "food_query": query if intent == "FOOD" else "",
        "food_data": "",
        "food_analysis": "",
        "health_impact": "",
        "messages": []
    }
    
    return state


# ============================================================================
# MAIN PROCESSING FUNCTIONS
# ============================================================================

def process_query(intent: str, query: str, image, chat_history, session_id: str):
    """
    Process a user query through the health assistant graph.
    
    Args:
        intent: "FOOD" or "MEDICAL"
        query: User's text query
        image: Optional image file path from Gradio
        chat_history: Current chat history
        session_id: Unique session identifier
    
    Returns:
        Updated chat history
    """
    if not query and not image:
        chat_history.append(format_chat_message("assistant", "❌ Please provide a query or an image."))
        return chat_history, gr.update(), gr.update()
    
    # Get or create session
    session = session_manager.reset_session(session_id)
    graph = session["graph"]
    config = session["config"]
    
    # Get image path if provided
    image_path = image if image else None
    
    # Add user message to chat
    user_msg = f"**Mode:** {'🍎 Food Analysis' if intent == 'FOOD' else '💊 Medical Consultation'}\n\n"
    if query:
        user_msg += f"**Query:** {query}"
    if image_path:
        user_msg += f"\n\n📷 *Image attached*"
    
    chat_history.append(format_chat_message("user", user_msg))
    chat_history.append(format_chat_message("assistant", "🔄 Processing your request..."))
    
    yield chat_history, gr.update(), gr.update(visible=False)
    
    # Create initial state
    initial_state = create_initial_state(intent, query, image_path)
    
    try:
        # Run the graph
        result = graph.invoke(initial_state, config)
        
        # Store session info
        session["state"] = result
        session["intent"] = intent
        
        # Check for emergency
        if result.get("is_emergency", False):
            emergency_msg = f"""
## 🚨 EMERGENCY DETECTED

{result.get('emergency_message', 'Please seek immediate medical attention!')}

---

### 📞 Emergency Contacts:
- **Emergency Services:** 911 (US) / 112 (EU) / 999 (UK)
- **Poison Control:** 1-800-222-1222 (US)

⚠️ **Do not wait - seek immediate medical care!**
"""
            chat_history[-1] = format_chat_message("assistant", emergency_msg)
            yield chat_history, gr.update(value=""), gr.update(visible=False)
            return
        
        # Check if graph is waiting for follow-up input
        graph_state = graph.get_state(config)
        if graph_state.next:
            # Graph is waiting for input
            session["awaiting_followup"] = True
            
            if graph_state.tasks and graph_state.tasks[0].interrupts:
                interrupt_value = graph_state.tasks[0].interrupts[0].value
                question = interrupt_value.get("question", "Please provide more information:")
                intent_type = interrupt_value.get("intent", "UNCLEAR")
                
                emoji = "🍎" if intent_type == "FOOD" else "🤖" if intent_type == "MEDICAL" else "❓"
                chat_history[-1] = format_chat_message("assistant", f"{emoji} **Agent:** {question}")
                
                yield chat_history, gr.update(value=""), gr.update(visible=True)
                return
        
        # Graph completed - display final result
        session["awaiting_followup"] = False
        final_intent = result.get("user_intent", intent)
        
        if final_intent == "FOOD":
            response = result.get("health_impact", "No analysis available.")
            title = "## 🍎 Food Analysis Results\n\n"
        else:
            response = result.get("final_explanation", "No recommendations available.")
            title = "## 💊 Medical Recommendation\n\n"
        
        chat_history[-1] = format_chat_message("assistant", title + response)
        
    except Exception as e:
        chat_history[-1] = format_chat_message("assistant", f"❌ An error occurred: {str(e)}")
    
    yield chat_history, gr.update(value=""), gr.update(visible=False)


def process_followup(followup_text: str, chat_history, session_id: str):
    """
    Process a follow-up response from the user.
    
    Args:
        followup_text: User's response to the follow-up question
        chat_history: Current chat history
        session_id: Unique session identifier
    
    Returns:
        Updated chat history
    """
    if not followup_text:
        return chat_history, gr.update(), gr.update(visible=True)
    
    session = session_manager.get_session(session_id)
    
    if not session["awaiting_followup"]:
        chat_history.append(format_chat_message("assistant", "❌ No pending question. Please start a new query."))
        return chat_history, gr.update(value=""), gr.update(visible=False)
    
    graph = session["graph"]
    config = session["config"]
    intent = session["intent"]
    
    # Add user response to chat
    chat_history.append(format_chat_message("user", followup_text))
    chat_history.append(format_chat_message("assistant", "🔄 Processing..."))
    
    yield chat_history, gr.update(value=""), gr.update(visible=True)
    
    try:
        # Resume graph with user's response
        result = graph.invoke(Command(resume=followup_text), config)
        session["state"] = result
        
        # Check for emergency
        if result.get("is_emergency", False):
            emergency_msg = f"""
## 🚨 EMERGENCY DETECTED

{result.get('emergency_message', 'Please seek immediate medical attention!')}

---

### 📞 Emergency Contacts:
- **Emergency Services:** 911 (US) / 112 (EU) / 999 (UK)
- **Poison Control:** 1-800-222-1222 (US)

⚠️ **Do not wait - seek immediate medical care!**
"""
            chat_history[-1] = format_chat_message("assistant", emergency_msg)
            session["awaiting_followup"] = False
            yield chat_history, gr.update(value=""), gr.update(visible=False)
            return
        
        # Check if graph is waiting for more input
        graph_state = graph.get_state(config)
        if graph_state.next:
            if graph_state.tasks and graph_state.tasks[0].interrupts:
                interrupt_value = graph_state.tasks[0].interrupts[0].value
                question = interrupt_value.get("question", "Please provide more information:")
                intent_type = interrupt_value.get("intent", "UNCLEAR")
                
                emoji = "🍎" if intent_type == "FOOD" else "🤖" if intent_type == "MEDICAL" else "❓"
                chat_history[-1] = format_chat_message("assistant", f"{emoji} **Agent:** {question}")
                
                yield chat_history, gr.update(value=""), gr.update(visible=True)
                return
        
        # Graph completed - display final result
        session["awaiting_followup"] = False
        final_intent = result.get("user_intent", intent)
        
        if final_intent == "FOOD":
            response = result.get("health_impact", "No analysis available.")
            title = "## 🍎 Food Analysis Results\n\n"
        else:
            response = result.get("final_explanation", "No recommendations available.")
            title = "## 💊 Medical Recommendation\n\n"
        
        chat_history[-1] = format_chat_message("assistant", title + response)
        
    except Exception as e:
        chat_history[-1] = format_chat_message("assistant", f"❌ An error occurred: {str(e)}")
        session["awaiting_followup"] = False
    
    yield chat_history, gr.update(value=""), gr.update(visible=False)


def clear_chat(session_id: str):
    """Clear the chat and reset the session."""
    session_manager.reset_session(session_id)
    return [], gr.update(value=""), gr.update(value=None), gr.update(visible=False, value="")


# ============================================================================
# GRADIO INTERFACE
# ============================================================================

def create_interface():
    """Create the Gradio interface."""
    
    with gr.Blocks(
        title="🏥 Health Assistant",
        theme=gr.themes.Soft(),
        css="""
        .main-header { text-align: center; margin-bottom: 20px; }
        .mode-selector { margin-bottom: 15px; }
        .submit-btn { background-color: #4CAF50 !important; }
        .clear-btn { background-color: #f44336 !important; }
        """
    ) as demo:
        
        # Session ID (hidden)
        session_id = gr.State(lambda: f"session_{int(time.time() * 1000)}")
        
        # Header
        gr.Markdown("""
        # 🏥 Health Assistant
        ### Medical Consultation & Food Analysis powered by AI
        
        ---
        """, elem_classes=["main-header"])
        
        with gr.Row():
            with gr.Column(scale=2):
                # Chat interface
                chatbot = gr.Chatbot(
                    label="Conversation",
                    height=500,
                    avatar_images=(None, "https://em-content.zobj.net/source/twitter/376/robot_1f916.png")
                )
                
                # Follow-up input (hidden initially)
                with gr.Row(visible=False) as followup_row:
                    followup_input = gr.Textbox(
                        label="Your Response",
                        placeholder="Type your response to the follow-up question...",
                        lines=2,
                        scale=4
                    )
                    followup_btn = gr.Button("📤 Send", variant="primary", scale=1)
                
            with gr.Column(scale=1):
                # Mode selection
                gr.Markdown("### 🎯 Select Mode")
                intent_selector = gr.Radio(
                    choices=[
                        ("🍎 Food Analysis", "FOOD"),
                        ("💊 Medical Consultation", "MEDICAL")
                    ],
                    value="MEDICAL",
                    label="What would you like help with?",
                    elem_classes=["mode-selector"]
                )
                
                # Query input
                gr.Markdown("### 📝 Your Query")
                query_input = gr.Textbox(
                    label="Enter your query",
                    placeholder="Describe your symptoms or enter food/ingredient to analyze...",
                    lines=3
                )
                
                # Image upload
                gr.Markdown("### 📷 Image (Optional)")
                image_input = gr.Image(
                    label="Upload an image",
                    type="filepath",
                    sources=["upload", "clipboard"]
                )
                
                # Buttons
                with gr.Row():
                    submit_btn = gr.Button("🚀 Analyze", variant="primary", elem_classes=["submit-btn"])
                    clear_btn = gr.Button("🗑️ Clear", variant="stop", elem_classes=["clear-btn"])
                
                # Examples
                gr.Markdown("### 💡 Examples")
                gr.Examples(
                    examples=[
                        ["MEDICAL", "I have a headache and fever since morning", None],
                        ["MEDICAL", "What is paracetamol used for?", None],
                        ["FOOD", "turmeric", None],
                        ["FOOD", "Is Coca-Cola healthy?", None],
                        ["FOOD", "sugar, palm oil, sodium benzoate, MSG", None],
                    ],
                    inputs=[intent_selector, query_input, image_input],
                    label="Click an example to try it"
                )
        
        # Instructions
        with gr.Accordion("📖 How to Use", open=False):
            gr.Markdown("""
            ## Instructions
            
            ### 🍎 Food Analysis Mode
            - Enter a **single ingredient** (e.g., "turmeric", "MSG", "aspartame")
            - Enter a **product name** (e.g., "Coca-Cola", "Oreos")
            - Enter an **ingredient list** (e.g., "sugar, palm oil, sodium benzoate")
            - Upload an **image of a food label** for analysis
            
            ### 💊 Medical Consultation Mode
            - Describe your **symptoms** (e.g., "I have a headache and fever")
            - Ask about a **medication** (e.g., "What is ibuprofen used for?")
            - Upload an **image** of visible symptoms for analysis
            - Answer follow-up questions to get personalized recommendations
            
            ### ⚠️ Important Disclaimers
            - This is for **informational purposes only**
            - **Always consult a healthcare professional** for medical advice
            - In case of **emergency**, call emergency services immediately
            
            ---
            
            **Built with:** LangGraph, LangChain, Gemini AI, and Gradio
            """)
        
        # Event handlers
        submit_btn.click(
            fn=process_query,
            inputs=[intent_selector, query_input, image_input, chatbot, session_id],
            outputs=[chatbot, query_input, followup_row]
        )
        
        followup_input.submit(
            fn=process_followup,
            inputs=[followup_input, chatbot, session_id],
            outputs=[chatbot, followup_input, followup_row]
        )
        
        followup_btn.click(
            fn=process_followup,
            inputs=[followup_input, chatbot, session_id],
            outputs=[chatbot, followup_input, followup_row]
        )
        
        clear_btn.click(
            fn=clear_chat,
            inputs=[session_id],
            outputs=[chatbot, query_input, image_input, followup_row]
        )
        
        # Also allow Enter key on query input
        query_input.submit(
            fn=process_query,
            inputs=[intent_selector, query_input, image_input, chatbot, session_id],
            outputs=[chatbot, query_input, followup_row]
        )
    
    return demo


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    demo = create_interface()
    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
