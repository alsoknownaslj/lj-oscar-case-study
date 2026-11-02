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
- **2026-11-02 — IDE SQL via `make db`; only plumbing models ported.** Lauren asked for
  the `oscar-case-study` commit 48ddedb setup here (run project SQL from a db extension
  in VS Code). Ported: `scripts/build_db.py`, `oscar_cs.db` (layer-ordered model loader,
  `scripts/sql.py` now uses it), `.vscode/extensions.json`, and the four data-plumbing
  views (`stg_ccs`, `stg_claim_lines`, `stg_prescription_drugs`, `int_claim_lines_ccs`) —
  these encode only facts already settled in CLAUDE.md (normalized join, exclusion
  flags, window marks). NOT ported: `dim_members` and the `fct_*` models — they carry
  the other repo's analysis framing (chronic rules, care-pattern cutoffs) and this
  repo's standing call is that no framing is pre-committed; they get proposed fresh
  during the analysis. Lauren can reopen if she wants them carried over.
- **2026-11-02 — `soul.md` added (Lauren).** Lauren asked for a soul file defining who
  the agent is. It lives at the repo root and is auto-imported by CLAUDE.md (same
  `@import` mechanism as the memory files) so every session loads it. Scope: stance,
  evidence habits, and voice only — operational rules stay in CLAUDE.md, which wins on
  any conflict (stated in both files). Two FILL-INs were left for Lauren and resolved
  the same day via `/fill-blanks`: the pair is named Ada (her pick, after Lovelace;
  chat-only — commit identity unchanged), and chat runs looser than reports, humor
  welcome. Rejected: `references/` (identity, not reference
  material) and `.claude/` (the humanize hook skips that tree, and soul.md should get
  the pass like any prose Lauren reads).
- **2026-11-01 — History reset (Lauren).** `main` was rebuilt to start at the split: one
  root commit holding the repo's starting state, then the post-split commits (humanize
  hooks, handoff, repo rules) — force-pushed, so pre-reset SHAs are gone. Pre-split
  history lives only in `oscar-case-study`. The "full-history duplicate" wording in the
  2026-11-01 duplication entry described the state before this reset.
- **2026-11-01 — Requirement-1 health-status framing (proposed by session; Lauren to
  ratify at report review).** Health status = per-member set of **CCS level-2 condition
  flags**, each **chronic** (≥2 distinct claim dates ≥30 days apart, per the
  healthcare-claims skill rule) or **one-off**, plus light utilization counts; the
  Symptoms/Z-code and Residual chapters are tracked but never conditions; unmapped codes
  are an explicit bucket. Round-trips to a one-sentence member description
  (oscar_cs.health_status.render_vignette). Rejected: single severity score (hides which
  conditions), utilization-only clustering (not clinically readable), CCS level 1 (too
  coarse) and level 3 (too sparse). Full justification + numbers:
  reports/2026-11-01_health-status-characterization.md. Per Lauren's 2026-10-31 call the
  framing was to be proposed during analysis — this is that proposal, open to reopening.
- **2026-11-02 — Canonical analysis window (Lauren): [2015-09-01, 2018-06-04], both
  tables.** One uniform time frame for all cross-table and population statistics, set to
  the intersection of real coverage (claims start 2015-09; both feeds taper out Apr–May
  2018 — the 2018-12 claims "end" is 6 stray rows, found while pricing this decision).
  Constants: `ANALYSIS_WINDOW_START/END` in src/oscar_cs/health_status.py. Price: claims
  lose 231 rows / 15 members; rx loses 311,585 pre-window fills (10.4%) / 10,322 members;
  in-window universe 282,734 (192,830 both, 52,321 claims-only, 37,583 rx-only).
  Pre-window rx may be used only as explicitly labeled history features, never silently.
  Caveat attached: Apr–May 2018 is taper-thin in both tables — partial coverage for
  recency-sensitive measures. Rejected: left-edge-only alignment (keeps a phantom
  rx-less claims tail that turned out to be 6 rows); per-analysis ad-hoc windows (the
  drift we were already accumulating).
- **2026-11-02 — Tier binning: median and quartile cuts rejected (Lauren).** Median
  splits leave a near-empty "mid" bin on tied integer counts; pooled quartiles collapse
  (the median member×class and member×condition pair is a single touch). Next session
  designs principled low/med/high bins for diagnostic-claim volume, fill volume, and the
  claims×rx contingency table — candidates: log-scale natural breaks, mixture models,
  clinically anchored cuts. Nothing binned is final until then.
- **2026-11-02 — Outlier policy (proposed by session; pending Lauren).** Remove no
  members: the extreme tail is a jointly structured sub-population (518 members above
  p99 on both volume axes vs ~19 under independence) and the brief asks for unusual-
  pattern detection, so it is a segment/deliverable. Use percentile fences, never raw
  IQR/z-scores (IQR flags ~10% here); default to rank/quantile statistics; cap displays
  at p99 with explicit labels; flag >p99 members as high utilizers. Rejected: trimming,
  winsorizing analysis data, raw-scale IQR fences.
