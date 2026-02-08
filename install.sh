#!/bin/bash
# CLI AI Installer
# Adds the Zsh integration to your .zshrc (idempotent)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHELL_SCRIPT="$SCRIPT_DIR/shell/cli_ai.zsh"
ZSHRC="$HOME/.zshrc"

# Check the shell script exists
if [[ ! -f "$SHELL_SCRIPT" ]]; then
  echo "Error: $SHELL_SCRIPT not found"
  exit 1
fi

# Check if already installed
if grep -q "cli_ai.zsh" "$ZSHRC" 2>/dev/null; then
  echo "CLI AI is already configured in $ZSHRC"
  echo "Source line: $(grep 'cli_ai.zsh' "$ZSHRC")"
  exit 0
fi

# Install Python package via pipx (isolated environment)
echo "Installing cli-ai Python package..."
if command -v pipx &>/dev/null; then
  pipx install "$SCRIPT_DIR" 2>&1 | tail -1
else
  echo "Error: pipx is not installed. Install it with: pip install --user pipx"
  exit 1
fi

# Add source line to .zshrc
echo "" >> "$ZSHRC"
echo "# CLI AI - natural language to shell commands (Alt+L)" >> "$ZSHRC"
echo "source $SHELL_SCRIPT" >> "$ZSHRC"

echo ""
echo "CLI AI installed successfully!"
echo "  Shortcut: Alt+L"
echo "  Config: $SHELL_SCRIPT"
echo ""
echo "Run 'source ~/.zshrc' or open a new terminal to activate."
