"""
Provider Factory for CLI AI.

Creates LLM provider instances based on configuration.
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any

from .providers.base_provider import BaseProvider
from .providers.groq_provider import GroqProvider
from . import config

logger = logging.getLogger(__name__)


class LLMType(str, Enum):
    """Available LLM provider types."""
    GROQ = "groq"
    CEREBRAS = "cerebras"


class ProviderFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create_provider(
        llm_type: LLMType,
        api_key: str,
        model: str,
        provider_config: Optional[Dict[str, Any]] = None,
    ) -> BaseProvider:
        """
        Create an LLM provider instance.

        Args:
            llm_type: Which provider to create
            api_key: API key for the provider
            model: Model name to use
            provider_config: Additional provider configuration

        Returns:
            Configured provider instance
        """
        provider_config = provider_config or {}

        if llm_type == LLMType.GROQ:
            return GroqProvider(
                api_key=api_key,
                model=model,
                timeout=provider_config.get("timeout", config.HTTP_TIMEOUT),
                **{k: v for k, v in provider_config.items() if k != "timeout"},
            )

        elif llm_type == LLMType.CEREBRAS:
            # Cerebras will be added in a later task; for now raise
            raise NotImplementedError("Cerebras provider not yet implemented")

        else:
            raise ValueError(f"Unknown LLM type: {llm_type}")

    @staticmethod
    def create_default_provider() -> BaseProvider:
        """
        Create the default provider (Groq) using config settings.

        Returns:
            Configured Groq provider instance

        Raises:
            ValueError: If GROQ_API_KEY is not configured
        """
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set. Configure it in .env file.")

        return ProviderFactory.create_provider(
            LLMType.GROQ,
            config.GROQ_API_KEY,
            config.GROQ_MODEL,
        )
