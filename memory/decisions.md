# Decisions — what was chosen, why, what was rejected

One dated entry per decision. Don't re-litigate without Lauren reopening it.

- **2026-10-31 — Repo layout & tooling.** Plain pip + `requirements.txt` + editable
  `src/oscar_cs` package; duckdb as the SQL engine over CSV/parquet (no warehouse); ruff +
  sqlfluff for tidiness. Rejected: poetry/uv (setup friction for a short case study),
  notebooks-only structure (kills reuse and review).
- **2026-10-31 — Data in git.** `claim_lines.csv` + `prescription_drugs.csv` stay out of
  git (GitHub 100 MB hard limit; 65/371 MB). `ccs.csv` committed once fetched (11 MB).
  Parquet cache is local-only for now; revisit if per-file sizes land < 95 MB and
  portability matters. Rejected: git-lfs (cost/complexity for one case study).
- **2026-10-31 — Skill selection** (non-overlapping by design):
  `humanize` = vendored [blader/humanizer](https://github.com/blader/humanizer) (MIT,
  ~63k stars). `simplify` = Claude Code built-in, nothing to install. EDA/SQL/stats/viz =
  Anthropic's official `data` plugin (knowledge-work-plugins marketplace) — one source
  instead of several overlapping community packs. ML/classification + healthcare = custom
  repo-local skills tailored to this case study. Rejected: community "data-scientist"
  mega-skills from aggregator directories (unverifiable quality, heavy overlap with the
  data plugin).
- **2026-10-31 — Memory design.** Four small memory files auto-imported via CLAUDE.md
  `@imports`, updated at moment-of-discovery + `/retro` sweep. Rejected: SessionStart hooks
  (fragile, needs trust review) and a single monolithic memory file (merge conflicts,
  no routing).
- **2026-11-01 — Repo duplicated → `oscar-case-study-2`; ML skill retired (Lauren).** This
  repo is a full-history duplicate of `alsoknownaslj/oscar-case-study` (left untouched).
  The repo-local `ml-classification` skill is removed here: modeling mechanics now come
  from Anthropic's `data` plugin (`data:analyze`, `data:statistical-analysis`), the same
  source that already covered EDA/SQL/stats/viz. There was no repo-local EDA skill to
  remove — EDA routed to `data:explore-data` from day one. The case-specific modeling
  guardrails (member-level splits, rx-only features, multi-label framing, AUROC/AUPRC over
  accuracy) stay in CLAUDE.md's common-mistakes list; the retired skill's fuller text
  lives on in the original repo if ever needed. `healthcare-claims` and `humanize` stay.
  No analysis or modeling work existed yet, so there was nothing to strip.
- **2026-11-01 — Humanize moved from convention to hooks (Lauren).** Two hooks in
  `.claude/settings.json`: SessionStart prints the humanize rule into context on every
  start/resume/clear/compact (so it survives compaction), and PostToolUse on Write|Edit
  nudges the moment a human-facing `.md` lands (memory/, data/ and .claude/ excluded —
  internal logs don't get the pass). Lauren asking for a hook outright supersedes the
  2026-10-31 hesitation about SessionStart hooks. Rejected: a blocking Stop hook (can't
  reliably tell whether prose was written → false blocks) and UserPromptSubmit injection
  (repeats the rule every turn for no gain).
- **2026-11-01 — Branch names + PR attribution (Lauren).** Branch names never include
  `claude/` and must say what the work is — a must in CLAUDE.md conventions. The
  "Generated with Claude Code" footer comes off PR descriptions via the supported
  `attribution.pr: ""` switch in `.claude/settings.json`, backed by a CLAUDE.md must for
  sessions that write PR bodies themselves. Rejected: a PreToolUse hook rewriting PR
  bodies — the attribution setting is the switch Claude Code actually honors, and body
  rewriting across the several PR-creating tools is fragile. Commit trailers unchanged.
