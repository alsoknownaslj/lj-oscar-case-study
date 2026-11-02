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
- **2026-11-02** — IDE SQL browsing: `make db` writes a self-contained `data/oscar.duckdb`
  (base tables copied in, model views created inside, no file paths). Written via
  `attach ... (storage_version 'v1.0.0')` because duckdb readers can't open newer storage
  formats and the SQLTools DuckDB driver bundles 1.3.2 (container duckdb is 2.0.0).
  Cross-version trap: `date_trunc` returns TIMESTAMP on older engines and DATE on newer —
  views that must read the same under both need an explicit `cast(... as date)`
  (`stg_prescription_drugs.fill_month`). The driver's `${workspaceFolder}` handling is
  commented out in its source, so connections are added once through the SQLTools UI;
  only `.vscode/extensions.json` is committed (`.vscode` stays gitignored otherwise).
  Ported from `oscar-case-study` commit 48ddedb; verified here by opening the file with
  duckdb 1.3.2 and running every view (99.89% coverage reproduced).
- **2026-11-02** — Cloud containers are ephemeral, so anything installed mid-session is
  gone in the next one (and registers only at the next CLI startup anyway, never in the
  running session). Lauren's skills persist via the environment's setup script instead
  (environment menu → Edit → Setup script): it curls pinned SKILL.md files into
  `~/.claude/skills/` (`i-have-adhd` @ 1ecea19 — vetted, markdown only; `humanize`
  @ 0ef9fe5) and makes ADHD mode always-on by writing the frontmatter-stripped ruleset to
  `~/.claude/i-have-adhd-always.md` plus an `@~/.claude/i-have-adhd-always.md` import in
  user-level `~/.claude/CLAUDE.md` — verified end-to-end with a fresh CLI run. The
  plugin's `touch ~/.claude/.i-have-adhd-always` flag works only through the plugin's own
  SessionStart hook, so it is inert with raw-skill installs. Also: skills with
  `disable-model-invocation: true` (i-have-adhd is one) are slash-only and never show up
  in the model-facing skill list — check `~/.claude/skills/` before concluding one is
  missing.
