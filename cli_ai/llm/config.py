"""
Configuration for CLI AI LLM services.

Loads API keys and model settings from .env file,
with optional overrides from ~/.config/cli-ai/config.toml.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from .. import config_file

logger = logging.getLogger(__name__)

# Load .env from project root (cli_ai/llm/config.py -> cli_ai/ -> project root)
_env_paths = [
    Path(__file__).parent.parent.parent / ".env",  # project_root/.env
    Path.cwd() / ".env",
]

_env_loaded = False
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        logger.debug(f"Loaded .env from {_env_path}")
        _env_loaded = True
        break

if not _env_loaded:
    logger.debug(".env not found; using environment variables if set.")

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

# Model defaults — config.toml overrides env vars, which override hardcoded defaults
_cfg_model = config_file.get("model")
GROQ_MODEL = _cfg_model or os.getenv("CLI_AI_GROQ_MODEL", "llama-3.3-70b-versatile")
CEREBRAS_MODEL = os.getenv("CLI_AI_CEREBRAS_MODEL", "llama-3.3-70b")

# Primary provider from config
PRIMARY_PROVIDER = config_file.get("provider")

# Timeouts (fast for CLI use)
HTTP_TIMEOUT = int(os.getenv("CLI_AI_TIMEOUT", "30"))
