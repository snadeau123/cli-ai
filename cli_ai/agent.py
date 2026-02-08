"""
Agent orchestration for CLI AI.

Builds messages, calls LLM with tools, handles multi-round tool loop,
returns a clean command string.
"""

import logging
from typing import Optional

from .prompts import build_system_prompt
from .tools import TOOL_SCHEMAS, execute_tool
from .llm.manager import LLMManager
from .llm.provider_factory import LLMType
from . import config_file

logger = logging.getLogger(__name__)


async def process_query(
    query: str,
    cwd: str,
    history: str = "",
    shell: str = "zsh",
    os_info: str = "linux",
    max_iterations: int | None = None,
) -> str:
    """
    Process a natural language query and return a shell command.

    Args:
        query: User's natural language request
        cwd: Current working directory
        history: Recent terminal history (last ~20 lines)
        shell: Current shell name
        os_info: OS identifier
        max_iterations: Max tool call rounds

    Returns:
        Shell command string (or # comment on error)
    """
    if max_iterations is None:
        max_iterations = config_file.get("max_iterations")

    # Build system prompt with context
    system_prompt = build_system_prompt(
        cwd=cwd, history=history, shell=shell, os_info=os_info
    )

    # Build user message
    messages = [{"role": "user", "content": query}]

    # Create tool handler bound to CWD
    async def tool_handler(name: str, args: dict) -> str:
        return await execute_tool(name, args, cwd)

    # Initialize LLM manager
    manager = LLMManager()
    await manager.initialize()

    try:
        result = await manager.generate(
            messages=messages,
            system_prompt=system_prompt,
            tools=TOOL_SCHEMAS,
            tool_handler=tool_handler,
            max_iterations=max_iterations,
            temperature=0.3,
            max_tokens=1024,
        )

        # Clean up the result — strip any markdown artifacts
        return _clean_command(result)

    except Exception as e:
        logger.error(f"Agent error: {e}")
        return f"# Error: {e}"
    finally:
        await manager.cleanup()


def _clean_command(text: str) -> str:
    """
    Clean LLM output to ensure it's a bare command.
    Strip markdown, backticks, function call artifacts, explanations.
    """
    import re

    text = text.strip()

    # Remove code block wrappers
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        lines = lines[1:-1] if len(lines) > 2 else lines
        text = "\n".join(lines).strip()

    # Remove single-line backtick wrapping
    if text.startswith("`") and text.endswith("`") and "\n" not in text:
        text = text.strip("`")

    # Remove function call artifacts (e.g. <function=name>{...}</function>)
    text = re.sub(r"<function=[^>]*>\{[^}]*\}</function>\s*", "", text)

    # Remove leading "$ " prompt markers
    if text.startswith("$ "):
        text = text[2:]

    # If multi-line, take the last non-empty line that looks like a command
    # (LLM sometimes prepends explanation before the actual command)
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) > 1:
        # Filter out lines that look like explanations (start with letters and contain spaces but no command chars)
        cmd_lines = [l for l in lines if not l.startswith("#") or l == lines[-1]]
        if cmd_lines:
            text = cmd_lines[-1]

    return text.strip()
