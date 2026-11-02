"""Regenerate the AUTO sections of README.md from the files they describe.

Each section sits between `<!-- AUTO:<name>:BEGIN -->` and `<!-- AUTO:<name>:END -->`
markers on their own lines; everything outside the markers is hand-written and left alone.

    python scripts/update_readme.py           # rewrite README.md if a section is stale
    python scripts/update_readme.py --check   # exit 1 if stale, write nothing

Stdlib only: the Claude Code hook (.claude/hooks/readme_sync.py) runs it before any
pip install has happened.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _docstring_first_line(path: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, SyntaxError):
        doc = None
    return (doc or "").strip().splitlines()[0].rstrip(".") if doc else "(no docstring)"


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def _notebook_title(path: Path) -> str:
    try:
        cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
    except (OSError, ValueError):
        cells = []
    for cell in cells:
        if cell.get("cell_type") == "markdown":
            for line in "".join(cell.get("source", [])).splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
    return path.stem


def section_make_targets() -> str:
    rows = ["| Command | Does |", "|---|---|"]
    for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):[^=]*?(?:##\s*(.*))?$", line)
        if m:
            rows.append(f"| `make {m[1]}` | {_md_cell(m[2] or '')} |")
    return "\n".join(rows)


def section_scripts() -> str:
    rows = ["| Script | What it does |", "|---|---|"]
    for path in sorted((ROOT / "scripts").glob("*.py")):
        rows.append(f"| `scripts/{path.name}` | {_md_cell(_docstring_first_line(path))} |")
    n_eda = len(list((ROOT / "scripts" / "eda").glob("*.py")))
    if n_eda:
        rows.append(
            f"| `scripts/eda/` ({n_eda} scripts) | exploratory analysis behind the EDA report |"
        )
    return "\n".join(rows)


def section_reports() -> str:
    lines = []
    # newest date first; same-day reports alphabetically
    reports = sorted((ROOT / "reports").glob("[0-9]*.md"), key=lambda p: p.name)
    reports.sort(key=lambda p: p.name[:10], reverse=True)
    for path in reports:
        title = next(
            (
                ln[2:].strip()
                for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.startswith("# ")
            ),
            path.stem,
        )
        extras = [
            p.suffix[1:].upper() for p in path.parent.glob(f"{path.stem}.*") if p.suffix != ".md"
        ]
        tail = (
            f" ({', '.join(f'[{e}](reports/{path.stem}.{e.lower()})' for e in sorted(extras))})"
            if extras
            else ""
        )
        lines.append(f"- [`{path.name}`](reports/{path.name}): {title}{tail}")
    for path in sorted((ROOT / "notebooks").glob("[0-9]*.ipynb")):
        lines.append(f"- [`notebooks/{path.name}`](notebooks/{path.name}): {_notebook_title(path)}")
    return "\n".join(lines) or "_No reports yet._"


def section_commands() -> str:
    lines = []
    for path in sorted((ROOT / ".claude" / "commands").glob("*.md")):
        m = re.search(r"^description:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        lines.append(f"- `/{path.stem}`: {m[1].strip() if m else ''}")
    return "\n".join(lines)


SECTIONS = {
    "reports": section_reports,
    "make": section_make_targets,
    "scripts": section_scripts,
    "commands": section_commands,
}


def render(text: str) -> str:
    for name, build in SECTIONS.items():
        begin, end = f"<!-- AUTO:{name}:BEGIN -->", f"<!-- AUTO:{name}:END -->"
        pattern = re.compile(rf"^{re.escape(begin)}$.*?^{re.escape(end)}$", re.S | re.M)
        if not pattern.search(text):
            raise SystemExit(f"README.md is missing the {begin} / {end} markers")
        replacement = f"{begin}\n{build()}\n{end}"
        text = pattern.sub(lambda _, r=replacement: r, text, count=1)
    return text


def main() -> int:
    current = README.read_text(encoding="utf-8")
    fresh = render(current)
    if fresh == current:
        return 0
    if "--check" in sys.argv:
        print("README.md AUTO sections are stale: run `make readme`", file=sys.stderr)
        return 1
    README.write_text(fresh, encoding="utf-8")
    print("README.md AUTO sections refreshed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
