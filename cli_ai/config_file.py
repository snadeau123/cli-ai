"""
Optional config file support for CLI AI.

Reads ~/.config/cli-ai/config.toml if it exists.
Missing config or invalid values fall back to defaults.
"""

import logging
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "cli-ai" / "config.toml"

# Defaults (match existing behavior)
DEFAULTS: Dict[str, Any] = {
    "provider": "groq",
    "model": None,  # None means use provider default
    "history_lines": 20,
    "max_iterations": 5,
    "max_file_lines": 500,
    "debug": False,
}

# Valid provider names
VALID_PROVIDERS = {"groq", "cerebras"}

_config: Dict[str, Any] = {}
_loaded = False


def _validate_int(value: Any, key: str, minimum: int = 1) -> int | None:
    """Validate an integer config value. Returns None if invalid."""
    try:
        val = int(value)
        if val < minimum:
            print(f"cli-ai: config '{key}' must be >= {minimum}, ignoring", file=sys.stderr)
            return None
        return val
    except (TypeError, ValueError):
        print(f"cli-ai: config '{key}' must be an integer, ignoring", file=sys.stderr)
        return None


def load_config() -> Dict[str, Any]:
    """
    Load config from TOML file, merging with defaults.

    Returns a dict with keys: provider, model, history_lines,
    max_iterations, max_file_lines.
    """
    global _config, _loaded

    if _loaded:
        return _config

    _config = dict(DEFAULTS)
    _loaded = True

    if not CONFIG_PATH.exists():
        logger.debug("No config file at %s, using defaults", CONFIG_PATH)
        return _config

    try:
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        print(f"cli-ai: error reading config: {e}", file=sys.stderr)
        return _config

    # [provider] section
    provider_section = data.get("provider", {})
    if isinstance(provider_section, dict):
        primary = provider_section.get("primary")
        if primary is not None:
            if primary in VALID_PROVIDERS:
                _config["provider"] = primary
            else:
                print(f"cli-ai: unknown provider '{primary}', ignoring", file=sys.stderr)

        model = provider_section.get("model")
        if model is not None:
            if isinstance(model, str) and model.strip():
                _config["model"] = model.strip()
            else:
                print("cli-ai: config 'model' must be a non-empty string, ignoring", file=sys.stderr)

    # [context] section
    context_section = data.get("context", {})
    if isinstance(context_section, dict):
        history_lines = context_section.get("history_lines")
        if history_lines is not None:
            val = _validate_int(history_lines, "history_lines")
            if val is not None:
                _config["history_lines"] = val

    # [tools] section
    tools_section = data.get("tools", {})
    if isinstance(tools_section, dict):
        max_iterations = tools_section.get("max_iterations")
        if max_iterations is not None:
            val = _validate_int(max_iterations, "max_iterations")
            if val is not None:
                _config["max_iterations"] = val

        max_file_lines = tools_section.get("max_file_lines")
        if max_file_lines is not None:
            val = _validate_int(max_file_lines, "max_file_lines", minimum=10)
            if val is not None:
                _config["max_file_lines"] = val

    # [debug] section
    debug_section = data.get("debug", {})
    if isinstance(debug_section, dict):
        enabled = debug_section.get("enabled")
        if isinstance(enabled, bool):
            _config["debug"] = enabled

    logger.debug("Loaded config: %s", _config)
    return _config


def get(key: str) -> Any:
    """Get a config value by key."""
    cfg = load_config()
    return cfg.get(key, DEFAULTS.get(key))


def reset():
    """Reset loaded config (for testing)."""
    global _config, _loaded
    _config = {}
    _loaded = False
