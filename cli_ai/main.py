"""
CLI AI entrypoint.

Reads JSON from stdin, calls the agent, prints the command to stdout.
"""

import asyncio
import json
import os
import sys


def main():
    """Read stdin, process query, print command."""
    try:
        # Read JSON from stdin
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(1)

        data = json.loads(raw)
        query = data.get("query", "")
        cwd = data.get("cwd", os.getcwd())
        shell = data.get("shell", "zsh")
        os_info = data.get("os", "linux")

        if not query:
            sys.exit(1)

        # Read terminal history from env var
        history = os.environ.get("CLI_AI_HISTORY", "")

        # Import here to keep startup fast if there's an early exit
        from .agent import process_query

        # Run the async agent
        result = asyncio.run(
            process_query(
                query=query,
                cwd=cwd,
                history=history,
                shell=shell,
                os_info=os_info,
            )
        )

        # Print only the command
        print(result, end="")
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
