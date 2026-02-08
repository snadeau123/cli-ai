"""
Read-only filesystem tools for CLI AI.

The AI can use these tools to inspect the local environment before
suggesting a shell command. All tools are read-only and path-safe.
"""

import glob
import os
import logging
from pathlib import Path
from typing import Dict, Any, List

from . import config_file

logger = logging.getLogger(__name__)

# Max constraints (config file can override MAX_FILE_LINES)
MAX_FILE_LINES = config_file.get("max_file_lines")
MAX_FILE_SIZE = 100 * 1024  # 100KB
MAX_SEARCH_RESULTS = 50
MAX_LIST_DEPTH = 3


def _resolve_safe_path(path_str: str, cwd: str) -> Path:
    """
    Resolve a path relative to CWD, blocking traversal above CWD.

    Raises:
        ValueError: If path escapes CWD
    """
    cwd_path = Path(cwd).resolve()
    target = (cwd_path / path_str).resolve()

    if not str(target).startswith(str(cwd_path)):
        raise ValueError(f"Path traversal blocked: {path_str}")

    return target


def _is_binary(path: Path) -> bool:
    """Check if a file appears to be binary."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except Exception:
        return True


def read_file(path: str, cwd: str) -> str:
    """Read contents of a text file (max 500 lines, 100KB)."""
    target = _resolve_safe_path(path, cwd)

    if not target.exists():
        return f"Error: File not found: {path}"
    if not target.is_file():
        return f"Error: Not a file: {path}"
    if target.stat().st_size > MAX_FILE_SIZE:
        return f"Error: File too large (>{MAX_FILE_SIZE // 1024}KB): {path}"
    if _is_binary(target):
        return f"Error: Binary file, cannot read: {path}"

    try:
        lines = target.read_text(errors="replace").splitlines()
        if len(lines) > MAX_FILE_LINES:
            content = "\n".join(lines[:MAX_FILE_LINES])
            return f"{content}\n\n[Truncated: showing {MAX_FILE_LINES}/{len(lines)} lines]"
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path: str, cwd: str, depth: int = 1) -> str:
    """List directory contents with optional depth."""
    target = _resolve_safe_path(path, cwd)

    if not target.exists():
        return f"Error: Directory not found: {path}"
    if not target.is_dir():
        return f"Error: Not a directory: {path}"

    depth = min(depth, MAX_LIST_DEPTH)
    lines = []

    def _walk(dir_path: Path, current_depth: int, prefix: str = ""):
        if current_depth > depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
            return

        for entry in entries:
            # Skip hidden files and common noise
            if entry.name.startswith(".") or entry.name in ("node_modules", "__pycache__", ".git"):
                continue

            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                if current_depth < depth:
                    _walk(entry, current_depth + 1, prefix + "  ")
            else:
                size = entry.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size // 1024}KB"
                else:
                    size_str = f"{size // (1024 * 1024)}MB"
                lines.append(f"{prefix}{entry.name}  ({size_str})")

    _walk(target, 1)
    return "\n".join(lines) if lines else "(empty directory)"


def search_files(pattern: str, path: str, cwd: str) -> str:
    """Search for files matching a glob pattern. Returns paths only."""
    target = _resolve_safe_path(path, cwd)

    if not target.exists() or not target.is_dir():
        return f"Error: Directory not found: {path}"

    search_pattern = str(target / "**" / pattern)
    matches = []

    for match in glob.iglob(search_pattern, recursive=True):
        match_path = Path(match)
        # Skip hidden, node_modules, __pycache__
        parts = match_path.parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts):
            continue

        try:
            rel = match_path.relative_to(target)
            matches.append(str(rel))
        except ValueError:
            continue

        if len(matches) >= MAX_SEARCH_RESULTS:
            break

    if not matches:
        return f"No files matching '{pattern}' found in {path}"

    result = "\n".join(matches)
    if len(matches) == MAX_SEARCH_RESULTS:
        result += f"\n\n[Truncated: showing first {MAX_SEARCH_RESULTS} results]"
    return result


def grep_files(pattern: str, path: str, cwd: str, ignore_case: bool = True) -> str:
    """Search file contents for a string pattern. Returns matching lines."""
    target = _resolve_safe_path(path, cwd)

    if not target.exists() or not target.is_dir():
        return f"Error: Directory not found: {path}"

    matches = []
    files_scanned = 0
    max_files = 200  # cap to keep it fast

    for file_path in sorted(target.rglob("*")):
        if files_scanned >= max_files:
            break

        # Skip dirs, hidden, noise
        parts = file_path.relative_to(target).parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__", "build",
               "dist", ".git") for p in parts):
            continue

        if not file_path.is_file():
            continue
        if file_path.stat().st_size > MAX_FILE_SIZE:
            continue
        if _is_binary(file_path):
            continue

        files_scanned += 1
        try:
            text = file_path.read_text(errors="replace")
        except Exception:
            continue

        compare_pattern = pattern.lower() if ignore_case else pattern
        for line_num, line in enumerate(text.splitlines(), 1):
            compare_line = line.lower() if ignore_case else line
            if compare_pattern in compare_line:
                rel = file_path.relative_to(target)
                matches.append(f"{rel}:{line_num}: {line.strip()}")
                if len(matches) >= MAX_SEARCH_RESULTS:
                    break
        if len(matches) >= MAX_SEARCH_RESULTS:
            break

    if not matches:
        return f"No matches for '{pattern}' in {path} ({files_scanned} files searched)"

    result = "\n".join(matches)
    if len(matches) == MAX_SEARCH_RESULTS:
        result += f"\n\n[Truncated: showing first {MAX_SEARCH_RESULTS} matches]"
    return result


def read_lines(path: str, start: int, end: int, cwd: str) -> str:
    """Read specific line range from a file (1-indexed)."""
    target = _resolve_safe_path(path, cwd)

    if not target.exists():
        return f"Error: File not found: {path}"
    if not target.is_file():
        return f"Error: Not a file: {path}"
    if _is_binary(target):
        return f"Error: Binary file: {path}"

    try:
        lines = target.read_text(errors="replace").splitlines()
        total = len(lines)

        # Clamp range
        start = max(1, start)
        end = min(end, total)

        if start > total:
            return f"Error: Start line {start} exceeds file length ({total} lines)"

        selected = lines[start - 1 : end]
        numbered = [f"{i}: {line}" for i, line in enumerate(selected, start=start)]
        header = f"Lines {start}-{end} of {total}:"
        return f"{header}\n" + "\n".join(numbered)
    except Exception as e:
        return f"Error reading lines: {e}"


# --- Tool Schemas (standard format for LLM) ---

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a text file. Returns the full file content (max 500 lines).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to working directory",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories at a path. Shows file sizes. Use depth>1 to see subdirectories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path, relative to working directory. Use '.' for current directory.",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels deep to list (default 1, max 3)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern (e.g., '*.py', 'Makefile', '*.json'). Returns file paths only, not contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '*.py', 'README*', '*.config.js')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in, relative to working directory. Default: '.'",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep_files",
        "description": "Search file contents for a text pattern (like grep). Returns matching lines with file paths and line numbers. Use this to find where a string appears in the codebase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text to search for in file contents (case-insensitive)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in, relative to working directory. Default: '.'",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "read_lines",
        "description": "Read a specific range of lines from a file (1-indexed). Useful for inspecting part of a large file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to working directory",
                },
                "start": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed)",
                },
                "end": {
                    "type": "integer",
                    "description": "Ending line number (inclusive)",
                },
            },
            "required": ["path", "start", "end"],
        },
    },
]


async def execute_tool(name: str, args: Dict[str, Any], cwd: str) -> str:
    """
    Execute a tool by name. Dispatcher for the LLM tool handler.

    Args:
        name: Tool name
        args: Tool arguments
        cwd: Current working directory for path resolution

    Returns:
        Tool result as string
    """
    if name == "read_file":
        return read_file(args["path"], cwd)
    elif name == "list_directory":
        return list_directory(args.get("path", "."), cwd, depth=args.get("depth", 1))
    elif name == "search_files":
        return search_files(args["pattern"], args.get("path", "."), cwd)
    elif name == "grep_files":
        return grep_files(args["pattern"], args.get("path", "."), cwd)
    elif name == "read_lines":
        return read_lines(args["path"], args["start"], args["end"], cwd)
    else:
        return f"Error: Unknown tool '{name}'"
