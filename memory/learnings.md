# Learnings — what worked, what failed, tool lessons

Append-only (newest last). One dated bullet per lesson; compact instead of deleting.

- **2026-10-31** — Google Drive connector caps `download_file_content` at **10 MB/file**;
  all three CSVs exceed it (ccs.csv misses by 0.4 MB). Large files must come via
  `scripts/fetch_data.py` (gdown, needs link-sharing) or manual download.
- **2026-10-31** — This cloud environment's network policy blocks `drive.google.com` and
  `drive.usercontent.google.com` (fix: environment menu → Edit → Network access → add both
  under Allowed domains). `www.googleapis.com` and `github.com` are open.
- **2026-10-31** — Oversized MCP tool results get written to a local file under
  `~/.claude/projects/.../tool-results/` instead of context; a `MAX_ALLOWED`-verbosity
  metadata call leaked a real ~1 MB head of `ccs.csv` that way (snippets are
  markdown-escaped: `\_`, `\[` — clean before parsing). Big-file snippets came back empty,
  so this trick only worked for ccs.
- **2026-10-31** — Cloud container stack: Python 3.13, **pandas 3.0.5** (str dtype default,
  copy-on-write always on). Code written for this repo must be pandas-3-safe; local
  environments may run pandas 2.x — the pin allows both.
- **2026-10-31** — GitHub from cloud sessions: attaching a repo grants **reads only** until
  the Claude GitHub App is installed for the repo's owner
  (<https://github.com/apps/claude/installations/select_target>) or GitHub is reconnected
  from claude.ai connector settings. Pushes 403'd until Lauren installed the app
  (resolved same day). Remote: `alsoknownaslj/oscar-case-study`; its auto-init README
  commit was merged (ours kept). Commits from cloud sessions use the
  `Claude <noreply@anthropic.com>` identity — Lauren's stop-hook enforces this so GitHub
  doesn't badge them Unverified (her email + no signature would).
- **2026-10-31** — gdown fails on restricted networks even with correct sharing: it
  downloads via `doc-XX-docs.googleusercontent.com` mirror hosts. curl against
  `drive.usercontent.google.com/download?id=…&export=download&confirm=t` needs only the
  two allowlisted Drive hosts. `fetch_data.py` is curl-first now.
- **2026-10-31** — duckdb `read_csv` sniffs the quote char from early rows only; this
  file's first quoted field is at row ~1.78M → hard parse error. Set `quote`/`escape`
  explicitly on every reader (done in build_cache, profile_data, sql.py).
- **2026-10-31** — Two self-inflicted bugs, not to repeat: (1) `approx_count_distinct`
  made unique keys look duplicated — always confirm keys with exact counts; (2) the
  profiler's AUTO-marker replace matched markers *mentioned in prose* — match markers on
  their own lines (line-anchored regex, fixed).
