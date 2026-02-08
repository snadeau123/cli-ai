"""
Groq Provider Implementation.

OpenAI-compatible provider with native tool calling support.
Primary provider for CLI AI due to fast inference + tool support.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Union, Any
from openai import AsyncOpenAI

from .base_provider import BaseProvider
from ..utils import (
    convert_to_standard_messages,
    convert_tools_to_openai_format,
    parse_openai_tool_calls,
    extract_text_from_content,
)

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """
    Groq provider using their OpenAI-compatible API.

    Supports:
    - Native: conversation, system, tools/functions, json_mode
    - Primary model: llama-3.3-70b-versatile
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 timeout: float = 30.0, **kwargs):
        super().__init__(api_key, model, timeout, **kwargs)
        self.base_url = kwargs.get("base_url", "https://api.groq.com/openai/v1")

    async def initialize(self) -> bool:
        """Initialize the Groq client."""
        try:
            # Clear proxy env vars — httpx doesn't support SOCKS without
            # socksio, and local HTTP proxies may be down. This is a short-lived
            # CLI process so clearing is safe.
            for k in ["ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
                       "HTTPS_PROXY", "https_proxy"]:
                os.environ.pop(k, None)

            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            logger.debug(f"Initialized Groq client with model: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            return False

    def supports_native(self, feature: str) -> bool:
        """Check if Groq natively supports a feature."""
        return {
            "conversation": True,
            "system": True,
            "tools": True,
            "json_mode": True,
        }.get(feature, False)

    def format_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Convert standard messages to Groq/OpenAI ChatCompletion format."""
        standard_messages = convert_to_standard_messages(messages, system_prompt)
        groq_messages = []

        for msg in standard_messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                groq_messages.append({"role": "system", "content": str(content)})

            elif role == "user":
                # Extract text if list content provided
                if isinstance(content, list):
                    text_content = extract_text_from_content(content)
                    groq_messages.append({"role": "user", "content": text_content})
                else:
                    groq_messages.append({"role": "user", "content": str(content)})

            elif role == "assistant":
                tool_calls_meta = msg.get("tool_calls")
                has_tool_calls = isinstance(tool_calls_meta, list) and tool_calls_meta

                # Content can be None when tool_calls are present
                if content is None or (content == "" and has_tool_calls):
                    content_value = None
                else:
                    content_value = str(content)

                assistant_msg = {"role": "assistant", "content": content_value}

                if has_tool_calls:
                    formatted_calls = []
                    for tc in tool_calls_meta:
                        try:
                            args = tc.get("input", {})
                            formatted_calls.append({
                                "id": tc.get("id"),
                                "type": "function",
                                "function": {
                                    "name": tc.get("name"),
                                    "arguments": json.dumps(args) if not isinstance(args, str) else args,
                                },
                            })
                        except Exception:
                            continue
                    if formatted_calls:
                        assistant_msg["tool_calls"] = formatted_calls

                groq_messages.append(assistant_msg)

            elif role == "tool":
                groq_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", "unknown"),
                    "content": str(content),
                })

        return groq_messages

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        tools: Optional[List[Dict[str, Any]]] = None,
        json_mode: bool = False,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate response using Groq API.

        Returns:
            str for text responses, dict with tool_calls for tool use.
        """
        if not self.client:
            raise RuntimeError("Groq client not initialized. Call initialize() first.")

        model_name = model_id or self.model
        groq_messages = self.format_messages(messages, system_prompt)

        # Build chat completion parameters
        chat_params = {
            "model": model_name,
            "messages": groq_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if json_mode:
            chat_params["response_format"] = {"type": "json_object"}

        if tools:
            chat_params["tools"] = convert_tools_to_openai_format(tools)
            chat_params["tool_choice"] = "auto"

        logger.debug(f"Groq request: model={model_name}, tools={len(tools) if tools else 0}")

        try:
            response = await self.client.chat.completions.create(**chat_params)

            # Check for tool calls in response
            if (tools and response.choices and response.choices[0].message
                    and response.choices[0].message.tool_calls):
                message = response.choices[0].message
                return {
                    "text_content": message.content or "",
                    "tool_calls": parse_openai_tool_calls(message.tool_calls),
                    "stop_reason": response.choices[0].finish_reason,
                }

            # Regular text response
            if response.choices and response.choices[0].message:
                text_content = response.choices[0].message.content or ""
                return text_content

            raise ValueError("No content in Groq response")

        except Exception as e:
            logger.error(f"Groq generate error: {e}")
            raise

    async def cleanup(self):
        """Clean up Groq client resources."""
        if self.client:
            await self.client.close()
        self.client = None
