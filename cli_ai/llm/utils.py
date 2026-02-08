"""
Utility functions for LLM providers.

Simplified for CLI AI: message conversion, tool format conversion,
JSON parsing, tool call parsing.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)


def convert_to_standard_messages(
    messages: Any, system_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convert various message formats to standard message format.

    Standard format:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        {"role": "tool", "content": "...", "tool_call_id": "..."}
    ]
    """
    if isinstance(messages, str):
        result = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        result.append({"role": "user", "content": messages})
        return result

    elif isinstance(messages, list):
        result = []
        has_system = any(
            msg.get("role") == "system" for msg in messages if isinstance(msg, dict)
        )
        if system_prompt and not has_system:
            result.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                logger.warning(f"Invalid message format: {msg}")
        return result

    else:
        logger.error(f"Unknown message format: {type(messages)}")
        return [{"role": "user", "content": str(messages)}]


def convert_tools_to_openai_format(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convert tools from standard format to OpenAI function calling format.

    Standard format:
        {"name": "...", "description": "...", "input_schema": {...}}
    OpenAI format:
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    openai_tools = []
    for tool in tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
            },
        }
        if "input_schema" in tool:
            openai_tool["function"]["parameters"] = tool["input_schema"]
        openai_tools.append(openai_tool)
    return openai_tools


def parse_openai_tool_calls(
    tool_calls: list,
) -> List[Dict[str, Any]]:
    """
    Parse OpenAI-format tool calls into standard format.

    Returns list of:
        {"id": "...", "name": "...", "input": {...}}
    """
    parsed = []
    for tc in tool_calls:
        args = tc.function.arguments
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except (json.JSONDecodeError, AttributeError):
            pass
        parsed.append(
            {
                "id": getattr(tc, "id", None),
                "name": getattr(tc.function, "name", None),
                "input": args,
            }
        )
    return parsed


def extract_text_from_content(content: Any) -> str:
    """
    Extract text from content (handles both string and list-of-parts formats).
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return " ".join(text_parts)
    else:
        return str(content)


def extract_json(text: str) -> Union[Dict, List, str]:
    """
    Extract and parse JSON from a text response.

    Handles: direct JSON, JSON in code blocks, JSON within surrounding text.
    """
    if not text:
        return {}

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try code blocks
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    for block in re.findall(code_block_pattern, text):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    # Try outermost JSON object
    for match in sorted(re.findall(r"\{[\s\S]*\}", text), key=len, reverse=True):
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # Try outermost JSON array
    for match in sorted(re.findall(r"\[[\s\S]*\]", text), key=len, reverse=True):
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    logger.warning(f"No valid JSON found in text: {text[:100]}")
    return text


def validate_tools_format(tools: List[Dict[str, Any]]) -> bool:
    """Validate that tools are in the expected standard format."""
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            return False
        if "name" not in tool or "description" not in tool:
            return False
        if "input_schema" in tool and not isinstance(tool["input_schema"], dict):
            return False
    return True
