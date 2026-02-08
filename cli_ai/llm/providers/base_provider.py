"""
Base Provider Abstract Class for LLM APIs.

Simplified for CLI AI: text generation with tool calling support only.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any
import logging

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    Abstract base class for all LLM providers.

    Supports:
    - Conversation history (multi-turn)
    - System prompts
    - Tool/function calling
    - JSON mode
    """

    def __init__(self, api_key: str, model: str, timeout: float = 30.0, **kwargs):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.config = kwargs
        self.client = None

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider client. Returns True on success."""
        pass

    @abstractmethod
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
        Generate a response from the LLM.

        Returns:
            str for text responses, dict with tool_calls for tool use responses.
        """
        pass

    @abstractmethod
    def supports_native(self, feature: str) -> bool:
        """Check if provider natively supports a feature (tools, json_mode)."""
        pass

    @abstractmethod
    def format_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Any:
        """Convert standard messages to provider-specific format."""
        pass

    def _add_system_to_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
    ) -> List[Dict[str, Any]]:
        """Prepend a system message if not already present."""
        if not system_prompt:
            return messages
        has_system = any(msg.get("role") == "system" for msg in messages)
        if has_system:
            return messages
        return [{"role": "system", "content": system_prompt}] + messages

    async def cleanup(self):
        """Clean up resources."""
        if hasattr(self.client, "close") and self.client:
            await self.client.close()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(model='{self.model}')"
