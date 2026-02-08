# CLI AI

Natural language to shell command translator. Type what you want in plain English, press **Alt+L**, and the text is replaced by the appropriate command.

```
find all markdown files containing hello  →  Alt+L  →  grep -rl "hello" --include="*.md" .
```

The AI has read-only access to your filesystem, so context-aware requests like "launch the backend" will inspect your project files and return the right command.

## Requirements

- Linux (Ubuntu) with Zsh
- Python 3.11+ (via `~/miniconda/` or system)
- [pipx](https://pipx.pypa.io/) (`pip install --user pipx`)
- Groq API key ([console.groq.com](https://console.groq.com))

## Install

```bash
cd ~/Projects/cli_ai

# Install the Python package (isolated via pipx)
pipx install .

# Add Alt+L binding to your shell
bash install.sh
source ~/.zshrc
```

### API key

`cli-ai` reads `GROQ_API_KEY` from the environment. Export it from a dotfile that your `.zshrc` sources (e.g. `~/.dotfiles.env`):

```bash
# ~/.dotfiles.env
export GROQ_API_KEY=gsk_...
```

```bash
# ~/.zshrc  (already present if you use dotfiles.env)
[ -f "$HOME/.dotfiles.env" ] && source "$HOME/.dotfiles.env"
```

A project-local `.env` file also works for development but is not required.

## Usage

Type a natural language request in your terminal and press **Alt+L**:

```
disk usage sorted by size        →  du -sh * | sort -rh
list all running docker containers  →  docker ps
launch the backend               →  npm run dev  (after inspecting package.json)
find python files with TODO      →  grep -rn "TODO" --include="*.py" .
```

The command replaces your input directly — just press Enter to run it.

### Direct invocation

```bash
echo '{"query":"list files","cwd":"/tmp","shell":"zsh","os":"linux"}' | cli-ai
```

## How It Works

1. **Alt+L** triggers a Zsh ZLE widget that captures your input
2. The widget collects context (last 20 lines of history, cwd, shell info) and sends it as JSON to the Python backend
3. The LLM (Groq, llama-3.3-70b-versatile) receives the query with read-only tool access
4. If needed, the AI inspects files (`read_file`, `list_directory`, `search_files`, `read_lines`) before answering — up to 5 tool rounds
5. The final command replaces your terminal input

On error, your original text is restored and a brief message is shown.

## Tools Available to the AI

| Tool | Purpose |
|------|---------|
| `read_file` | Read a text file (max 500 lines) |
| `list_directory` | List files/dirs with sizes |
| `search_files` | Glob-based file search |
| `read_lines` | Read specific line range |

All tools are read-only with path traversal protection.

## Configuration

### API key (required)

Set `GROQ_API_KEY` as an environment variable (see [Install](#install) above).

### ~/.config/cli-ai/config.toml (optional)

```toml
[provider]
primary = "groq"                    # "groq" or "cerebras"
model = "llama-3.3-70b-versatile"

[context]
history_lines = 20                  # terminal history lines to include

[tools]
max_iterations = 5                  # max tool call rounds
max_file_lines = 500                # max lines per file read

[debug]
enabled = true                      # log full LLM conversations
```

All settings are optional — defaults work out of the box.

When `debug.enabled = true`, every LLM request/response (including the full message history and tool calls) is appended to `~/.local/share/cli-ai/debug.log`.

## Project Structure

```
cli_ai/
├── cli_ai/
│   ├── main.py              # Entrypoint: stdin → agent → stdout
│   ├── agent.py             # Tool loop orchestration
│   ├── tools.py             # Read-only filesystem tools
│   ├── prompts.py           # System prompt template
│   ├── config_file.py       # Optional TOML config
│   └── llm/
│       ├── manager.py       # LLM manager with tool loop
│       ├── config.py        # API keys and model settings
│       ├── provider_factory.py
│       ├── utils.py
│       └── providers/
│           ├── base_provider.py
│           └── groq_provider.py
├── shell/
│   └── cli_ai.zsh           # Zsh integration (Alt+L)
├── tests/
│   └── test_config_file.py
├── install.sh               # Adds source line to .zshrc
└── pyproject.toml
```

## License

MIT
