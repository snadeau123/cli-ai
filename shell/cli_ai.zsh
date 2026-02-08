# CLI AI - Zsh Integration
# Bind Alt+L to translate natural language to shell commands via LLM
#
# Usage: Type a request in natural language, press Alt+L, get the command.
# Example: "find all python files containing TODO" → grep -rn "TODO" --include="*.py" .

_cli_ai_zle() {
  # Only act if there's text in the buffer
  if [[ -z "$BUFFER" ]]; then
    return
  fi

  local original="$BUFFER"

  # Build JSON payload with query and context
  local json_payload
  json_payload=$(python3 -c "
import json, os
print(json.dumps({
    'query': $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$BUFFER"),
    'cwd': os.getcwd(),
    'shell': 'zsh',
    'os': 'linux'
}))
" 2>/dev/null)

  if [[ -z "$json_payload" ]]; then
    zle -M "cli-ai: failed to build request"
    return
  fi

  # Collect last 20 lines of terminal history
  local history_context
  history_context=$(fc -ln -20 2>/dev/null | head -20)

  # Call the Python backend
  local result
  result=$(echo "$json_payload" | CLI_AI_HISTORY="$history_context" cli-ai 2>/dev/null)
  local exit_code=$?

  if [[ $exit_code -eq 0 && -n "$result" ]]; then
    # Success: replace buffer with the command
    BUFFER="$result"
    CURSOR=${#BUFFER}
  else
    # Error: restore original buffer and show message
    BUFFER="$original"
    CURSOR=${#BUFFER}
    zle -M "cli-ai: request failed (exit $exit_code)"
  fi

  zle redisplay
}

# Register the widget and bind to Alt+L
zle -N _cli_ai_zle
bindkey '\el' _cli_ai_zle
