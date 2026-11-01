#!/bin/bash
# SessionStart hook: print the humanize rule into context at every session
# start, resume, clear and compact, so the rule survives context loss.
set -euo pipefail
cat <<'RULE'
HUMANIZE RULE (hook-enforced, every session): any prose a human will read -
reports, README, references docs, notebook markdown - gets a pass through the
`humanize` skill (Skill tool, skill: "humanize") as the FINAL step before it
is called done. Run it unprompted; it is this project's standing rule.
RULE
