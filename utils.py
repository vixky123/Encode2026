"""
Utility functions for the Health Assistant application.
"""

import base64
from pathlib import Path
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel


def encode_image(image_path: str) -> str:
    """Encode image to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    """Get MIME type based on file extension"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    return mime_types.get(ext, "image/jpeg")


def create_message_with_image(text: str, image_path: str = None) -> HumanMessage:
    """Create a HumanMessage with optional image attachment"""
    if image_path and Path(image_path).exists():
        image_data = encode_image(image_path)
        mime_type = get_image_mime_type(image_path)
        
        content = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
            }
        ]
        return HumanMessage(content=content)
    else:
        return HumanMessage(content=text)


def create_message_with_image_bytes(text: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> HumanMessage:
    """Create a HumanMessage with image from bytes (for Gradio)"""
    if image_bytes:
        image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
        content = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
            }
        ]
        return HumanMessage(content=content)
    else:
        return HumanMessage(content=text)


def create_agent_node(agent, name):
    """Create an agent node wrapper"""
    def agent_node(state):
        result = agent.invoke(state)

        if not isinstance(result, dict):
            result = {"messages": [result], "sender": name}

        return result

    return agent_node


def create_agent(system_prompt: str, llm: BaseLanguageModel):
    """Create an agent with given prompt and LLM"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])
    return prompt | llm
