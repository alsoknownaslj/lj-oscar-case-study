# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-11-01 (requirement-1 analysis session, cloud).**

## Where things stand

Requirement 1 is built and written up, on branch **`req1-health-status`** (pushed; not
merged to main — Lauren reviews first). The session was handed a `claude/...` branch and
moved to a descriptive one per the CLAUDE.md branch must.

- **Characterization (proposed, pending Lauren's ratification — see memory/decisions.md
  2026-11-01):** per-member CCS level-2 condition flags, chronic (≥2 dates ≥30 days
  apart) vs one-off; Symptoms/Z-code + Residual chapters tracked but never conditions;
  unmapped codes an explicit counted bucket. Headlines: 245,165 members characterized,
  35.1% with ≥1 chronic condition, median 2 conditions, 99.89% CCS row coverage.
- **Code:** `scripts/build_health_status.py` (pipeline + stats + 3 deterministic
  vignettes) → `data/processed/{member_conditions,member_health_status}.parquet` +
  `health_status_stats.json` (all local-only; rebuild anytime). Policy constants in
  `src/oscar_cs/health_status.py`; parameterized queries in `sql/`; shared duckdb views
  in `src/oscar_cs/db.py` (scripts/sql.py now uses it). Tests cover the chronic rule
  incl. a SQL↔Python parity check (`make test`: 10 pass).
- **Report (humanize pass done):** `reports/2026-11-01_health-status-characterization.md`
  + 2 figures (dataviz-skill palette, validated). Vignette member ids masked there; the
  build script prints real ones.
- **Doc corrections:** claims volume ramps from **2015-09** (not 2015-12) — CLAUDE.md,
  data dictionary and data-quirks updated; new junk codes `99999`/`KHDX` logged.

Environment notes: fresh container rebuilt cleanly (`make fetch cache profile` — profile
reproduced the dictionary byte-identically; Drive domains were allowed). The 72-hour
window question is Lauren's to track; analysis work started this session on her go-ahead.

## Next concrete step

1. **Lauren reviews** the report + framing (ratify or amend the 2026-11-01 decision;
   likeliest amendment: re-bucket "Immunizations and screening" out of conditions — it's
   #1 in "What more time buys").
2. **Requirement 2 (rx-only model):** labels come from `member_health_status.parquet` /
   `member_conditions.parquet` (rebuild via `python scripts/build_health_status.py`).
   Guardrails: CLAUDE.md common mistakes 4–6 and 8 (member-level split, rx-only features,
   multi-label one-vs-rest, window alignment — rx ends 2018-06, 6 months before claims).
   Drug→condition strength tiers: `references/domain-notes.md` + healthcare-claims skill.
   Mechanics: `data:analyze` + `data:statistical-analysis`. Target conditions to start:
   chronic flags for drug-managed conditions (diabetes, hypertension, lipid disorders,
   asthma/COPD, mental illness, cancer) — expect performance to follow the tier ladder.
3. **Final deliverable assembly** (after req 2): supporting notebook that reproduces
   every number (jupyter isn't in requirements.txt — uncomment/add when needed), then a
   combined ~2-page report per references/report-style.md.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`
- `make fetch` (needs Drive link-sharing + the two Drive domains allowed — both held on
  2026-11-01), `make cache`; `make profile` only to re-verify.
- Commits: identity `Claude <noreply@anthropic.com>`; branch names descriptive, never
  `claude/...`; no PRs unless Lauren asks.
- `/fill-blanks`, `/retro`, `/remember` + humanize hooks register in sessions on this repo.
