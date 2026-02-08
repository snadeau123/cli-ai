"""
Simplified LLM Manager for CLI AI.

Provides a unified interface for LLM generation with multi-round tool calling.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union

from .provider_factory import ProviderFactory, LLMType
from .providers.base_provider import BaseProvider
from . import config
from .. import config_file

logger = logging.getLogger(__name__)

# Debug log directory
_DEBUG_LOG_DIR = Path.home() / ".local" / "share" / "cli-ai"
_DEBUG_LOG_FILE = _DEBUG_LOG_DIR / "debug.log"


def _debug_enabled() -> bool:
    return bool(config_file.get("debug"))


def _debug_log(label: str, data: Any) -> None:
    """Append a timestamped entry to the debug log file."""
    if not _debug_enabled():
        return
    try:
        _DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_DEBUG_LOG_FILE, "a") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            f.write(f"\n{'='*72}\n")
            f.write(f"[{ts}] {label}\n")
            f.write(f"{'='*72}\n")
            if isinstance(data, (dict, list)):
                f.write(json.dumps(data, indent=2, default=str))
            else:
                f.write(str(data))
            f.write("\n")
    except Exception:
        pass  # never break the CLI for debug logging


class LLMManager:
    """
    Manages LLM provider lifecycle and generation with tool calling support.
    """

    def __init__(self):
        self.providers: Dict[LLMType, BaseProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """Initialize available providers from config."""
        if config.GROQ_API_KEY:
            try:
                self.providers[LLMType.GROQ] = ProviderFactory.create_provider(
                    LLMType.GROQ, config.GROQ_API_KEY, config.GROQ_MODEL
                )
                logger.debug(f"Created Groq provider: {config.GROQ_MODEL}")
            except Exception as e:
                logger.error(f"Failed to create Groq provider: {e}")
        else:
            logger.warning("GROQ_API_KEY not set.")

    async def initialize(self):
        """Initialize all provider clients."""
        for llm_type, provider in self.providers.items():
            try:
                if not await provider.initialize():
                    logger.error(f"Failed to initialize {llm_type.value}")
            except Exception as e:
                logger.error(f"Error initializing {llm_type.value}: {e}")

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        llm_type: LLMType = LLMType.GROQ,
        model_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_handler: Optional[Callable] = None,
        max_iterations: int = 5,
        **kwargs,
    ) -> str:
        """
        Generate a response, handling multi-round tool calling.

        Args:
            messages: Conversation messages
            llm_type: Provider to use
            model_id: Override model
            system_prompt: System prompt
            max_tokens: Max tokens to generate
            temperature: Temperature
            tools: Tool definitions (standard format)
            tool_handler: async callable(name, input) -> str
            max_iterations: Max tool call rounds
            **kwargs: Extra provider params

        Returns:
            Final text response after all tool rounds complete.
        """
        if llm_type not in self.providers:
            return f"# Error: {llm_type.value} provider not available"

        provider = self.providers[llm_type]
        conversation = list(messages)

        _debug_log("CONVERSATION START", {
            "system_prompt": system_prompt,
            "messages": conversation,
            "tools": [t.get("name") for t in tools] if tools else None,
            "max_iterations": max_iterations,
        })

        for iteration in range(max_iterations):
            _debug_log(f"REQUEST iteration={iteration+1}/{max_iterations}", {
                "messages": conversation,
                "tools_enabled": bool(tools and tool_handler),
            })

            try:
                response = await provider.generate(
                    messages=conversation,
                    system_prompt=system_prompt,
                    model_id=model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools if tool_handler else None,
                    **kwargs,
                )
            except Exception as e:
                _debug_log(f"ERROR iteration={iteration+1}", str(e))
                logger.error(f"LLM generate error (iteration {iteration}): {e}")
                return f"# Error: {e}"

            _debug_log(f"RESPONSE iteration={iteration+1}", response)

            # If response is a string, no tool calls — we're done
            if isinstance(response, str):
                return response

            # If response is a dict with tool_calls, execute them
            if isinstance(response, dict) and response.get("tool_calls"):
                tool_calls = response["tool_calls"]
                text_content = response.get("text_content", "")

                logger.debug(
                    f"Iteration {iteration + 1}: {len(tool_calls)} tool call(s)"
                )

                # Add assistant message with tool_calls to conversation
                assistant_msg = {
                    "role": "assistant",
                    "content": text_content or None,
                    "tool_calls": tool_calls,
                }
                conversation.append(assistant_msg)

                # Execute each tool and add results
                for tc in tool_calls:
                    try:
                        result = await tool_handler(tc["name"], tc["input"])
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": str(result),
                        })
                    except Exception as e:
                        logger.error(f"Tool {tc['name']} error: {e}")
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": f"Error: {e}",
                        })

                # Continue loop — LLM will see tool results and may call more tools
                continue

            # Unexpected response format
            if isinstance(response, dict):
                return response.get("text_content", str(response))

            return str(response)

        # Max iterations reached — ask LLM for final answer without tools.
        # Inject a user message to break the tool-calling pattern, otherwise
        # the model (primed by many tool-call messages) keeps generating tool
        # calls even when tool_choice is none, which the API rejects.
        logger.warning(f"Max tool iterations ({max_iterations}) reached, forcing final answer")
        conversation.append({
            "role": "user",
            "content": (
                "You have used all available tool calls. "
                "Based on the information gathered, provide your final answer now. "
                "Do NOT call any tools. Return ONLY the shell command."
            ),
        })
        _debug_log("FINAL REQUEST (tools disabled)", {"messages": conversation})
        try:
            final = await provider.generate(
                messages=conversation,
                system_prompt=system_prompt,
                model_id=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=None,
                **kwargs,
            )
            _debug_log("FINAL RESPONSE", final)
            return final if isinstance(final, str) else str(final)
        except Exception as e:
            _debug_log("FINAL ERROR", str(e))
            return f"# Error after max iterations: {e}"

    async def cleanup(self):
        """Clean up all providers."""
        for provider in self.providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
