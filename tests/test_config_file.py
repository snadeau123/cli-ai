"""Tests for config_file module."""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from cli_ai import config_file


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config state before each test."""
    config_file.reset()
    yield
    config_file.reset()


class TestDefaults:
    """Missing config uses sensible defaults."""

    def test_defaults_when_no_file(self):
        with patch.object(config_file, "CONFIG_PATH", Path("/nonexistent/config.toml")):
            cfg = config_file.load_config()

        assert cfg["provider"] == "groq"
        assert cfg["model"] is None
        assert cfg["history_lines"] == 20
        assert cfg["max_iterations"] == 5
        assert cfg["max_file_lines"] == 500

    def test_get_returns_defaults(self):
        with patch.object(config_file, "CONFIG_PATH", Path("/nonexistent/config.toml")):
            assert config_file.get("provider") == "groq"
            config_file.reset()
            assert config_file.get("history_lines") == 20


class TestLoadsToml:
    """Reads ~/.config/cli-ai/config.toml if it exists."""

    def test_reads_all_settings(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text(
            '[provider]\nprimary = "cerebras"\nmodel = "my-model"\n\n'
            "[context]\nhistory_lines = 30\n\n"
            "[tools]\nmax_iterations = 3\nmax_file_lines = 200\n"
        )
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["provider"] == "cerebras"
        assert cfg["model"] == "my-model"
        assert cfg["history_lines"] == 30
        assert cfg["max_iterations"] == 3
        assert cfg["max_file_lines"] == 200

    def test_partial_config_merges_with_defaults(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text("[context]\nhistory_lines = 50\n")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["history_lines"] == 50
        # Unset values use defaults
        assert cfg["provider"] == "groq"
        assert cfg["max_iterations"] == 5

    def test_empty_config_uses_defaults(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text("")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg == config_file.DEFAULTS


class TestValidation:
    """Invalid values ignored with stderr warning."""

    def test_invalid_provider_ignored(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text('[provider]\nprimary = "openai"\n')
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["provider"] == "groq"  # default
        assert "unknown provider" in capsys.readouterr().err

    def test_invalid_int_ignored(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text('[context]\nhistory_lines = "not_a_number"\n')
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["history_lines"] == 20  # default
        assert "must be an integer" in capsys.readouterr().err

    def test_negative_int_ignored(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text("[tools]\nmax_iterations = -1\n")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["max_iterations"] == 5  # default
        assert "must be >=" in capsys.readouterr().err

    def test_empty_model_ignored(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text('[provider]\nmodel = ""\n')
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["model"] is None  # default
        assert "non-empty string" in capsys.readouterr().err

    def test_corrupt_toml_uses_defaults(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text("this is not valid toml {{{}}")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg == config_file.DEFAULTS
        assert "error reading config" in capsys.readouterr().err

    def test_max_file_lines_minimum_10(self, tmp_path, capsys):
        config = tmp_path / "config.toml"
        config.write_text("[tools]\nmax_file_lines = 5\n")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg = config_file.load_config()

        assert cfg["max_file_lines"] == 500  # default
        assert "must be >= 10" in capsys.readouterr().err


class TestCaching:
    """Config is loaded once and cached."""

    def test_load_is_cached(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text("[context]\nhistory_lines = 99\n")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg1 = config_file.load_config()
            # Modify the file — should not affect cached result
            config.write_text("[context]\nhistory_lines = 1\n")
            cfg2 = config_file.load_config()

        assert cfg1["history_lines"] == 99
        assert cfg2["history_lines"] == 99

    def test_reset_clears_cache(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text("[context]\nhistory_lines = 99\n")
        with patch.object(config_file, "CONFIG_PATH", config):
            cfg1 = config_file.load_config()
            config_file.reset()
            config.write_text("[context]\nhistory_lines = 1\n")
            cfg2 = config_file.load_config()

        assert cfg1["history_lines"] == 99
        assert cfg2["history_lines"] == 1
