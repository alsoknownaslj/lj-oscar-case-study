#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit|NotebookEdit|Bash): keep README.md in sync.

1. Re-runs scripts/update_readme.py after every file-changing tool call, so the AUTO
   sections (reports, make targets, scripts, slash commands) never drift. It only
   writes when something actually changed.
2. When a file that the README's hand-written prose depends on changes, it nudges the
   session to review that prose too (once per file per session).

Stdlib only - this runs before any pip install.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])

# Files the hand-written README sections (status, setup, layout) lean on.
PROSE_SOURCES = {
    "memory/handoff.md": "the Status section",
    "requirements.txt": "the Setup section",
    "pyproject.toml": "the Setup section",
    "scripts/fetch_data.py": "the data-fetching steps",
    ".gitignore": "the note on what stays out of git",
}


def _relpath(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return path.replace("\\", "/")


def _first_time(session_id: str, rel: str) -> bool:
    marker = Path(tempfile.gettempdir()) / f"readme-sync-{session_id or 'nosession'}.txt"
    seen = set(marker.read_text().splitlines()) if marker.exists() else set()
    if rel in seen:
        return False
    marker.write_text("\n".join(seen | {rel}))
    return True


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    rel = _relpath(str((payload.get("tool_input") or {}).get("file_path") or ""))

    notes = []
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_readme.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        notes.append(f"README sync failed: {result.stderr.strip() or result.stdout.strip()}")
    elif "refreshed" in result.stdout:
        notes.append(
            "README sync hook: regenerated the AUTO sections of README.md from the files "
            "they describe. Commit README.md along with this change."
        )

    if rel in PROSE_SOURCES and _first_time(str(payload.get("session_id") or ""), rel):
        notes.append(
            f"README sync hook: {rel} changed, and README.md's hand-written prose covers "
            f"it in {PROSE_SOURCES[rel]}. Check that section still matches, update it if "
            "not, and humanize any prose you change."
        )

    if notes:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": " ".join(notes),
                    },
                    "suppressOutput": True,
                }
            )
        )


if __name__ == "__main__":
    main()
