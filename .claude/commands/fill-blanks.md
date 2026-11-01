---
description: Walk Lauren through the remaining FILL-IN blanks, one at a time
---

Collect and resolve the project's open blanks with Lauren:

1. `grep -rn "FILL-IN" CLAUDE.md references/ memory/` — gather every open blank, grouped
   by file.
2. Go through them one at a time, highest-leverage first (report shape and case-study
   framing before aesthetics). Ask one clear question each — offer sensible options plus
   your recommendation (use AskUserQuestion where available). Never answer one yourself.
3. For each answer: replace the FILL-IN block in place with the decided content (concise,
   in the document's voice), and mirror anything preference-shaped into
   `memory/preferences.md` with today's date.
4. End with a summary: what got filled, what Lauren deferred, what remains open.
