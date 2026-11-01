#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit): when a human-facing markdown file is written,
remind the session to run the `humanize` skill before the write-up is called done.

Stdlib only - this runs before any pip install. Paths under memory/, data/ and
.claude/ are internal, not reader-facing prose, so they get no reminder.
"""

import json
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    path = str((payload.get("tool_input") or {}).get("file_path") or "")
    norm = path.replace("\\", "/")
    if not norm.endswith(".md"):
        return
    if {".claude", "memory", "data"} & set(norm.split("/")):
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"Humanize hook: {path} looks like human-facing prose. "
                        "Run the `humanize` skill over it before calling this "
                        "write-up done (standing project rule)."
                    ),
                },
                "suppressOutput": True,
            }
        )
    )


if __name__ == "__main__":
    main()
