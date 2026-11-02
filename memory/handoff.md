# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-11-02 late afternoon (deadline-day session: definition ratified, both
requirements built, final report written). The 72-hour window closes 5pm today
(Lauren's local time) — the deliverable is DONE and on `main` pending her read.**

## Where things stand

- **THE DELIVERABLE is `reports/2026-11-02_case-study-report.md`** (Lauren's combined
  structure, humanized, no semicolons), exported as `reports/2026-11-02_case-study-report.pdf`
  (14 pages, figures embedded). `notebooks/01_final_report.ipynb` reproduces every number
  (executed clean, masked ids only). Figures: `reports/figures/2026-11-02_final_fig01–04`.
- **Deleted at Lauren's request (2026-11-02, after the deadline):** the two superseded
  drafts (`2026-11-02_final-report.md`, `2026-11-02_data-analysis-report.md`) and the
  EDA-days session log (`2026-11-02_session-export.md`), on branch
  `remove-superseded-reports` with the PR left open and unmerged by her instruction. Git
  history keeps all three.
- **Health status v2 is ratified and implemented** (rules in `memory/decisions.md`
  2026-11-02): member × CCS level-2 conditions shaped one_off/episode/chronic (180d
  span boundary), reinfection-trap cap (injuries + infections never chronic; Viral
  infection exempt; TB/spinal-cord cost noted in the report), R-code symptoms track at
  level 3, Z/immunizations/residual/unmapped as counted non-condition buckets,
  head/tail-breaks tiers + >p99 flags (outlier policy ratified). Pipeline:
  `scripts/build_health_status.py` (11s); constants in `src/oscar_cs/health_status.py`;
  16 unit tests pin the boundaries and SQL↔Python agreement.
- **Requirement 2 is built**: `scripts/build_rx_model.py` (16s) — 15 per-condition
  logistic regressions, AUROC 0.80–0.97, AUPRC 8–41x prevalence, calibration near the
  diagonal, coefficients recover the pharmacology. 37,583 rx-only members scored
  (ranked lists, not thresholds — see learnings).
- **Headline numbers** (all in the report + stats json): 245,151 claims members; mix
  41.5% one-off-only / 31.5% episodic / 15.2% chronic / 9.8% admin-unmapped-only /
  2.0% symptom-only; 4,941 symptom-only members; tier diagonal lift 6.04x high-high;
  518 joint-p99 vs 19.6 expected.
- Everything is merged to `main`. Branches `model-split-preference` and
  `case-study-final` are merged; cloud sessions can't delete remote branches (Lauren
  can, in the GitHub UI). The old draft report
  (`reports/2026-11-01_health-status-characterization.md`) is superseded by the final
  report but kept for the record.

## If Lauren reopens anything

1. Her review of the final report may produce edits — the open questions she may rule
   on: TB/HIV-style exemption list for the cap; whether rx persistence should co-define
   chronic; symptom-only segment framing.
2. "What more time buys" is ranked in the report (prospective split first) — any item
   can become the next session's work.
3. Model-split rule (preferences, 2026-11-02): planning/brainstorming on Opus 5.5 max;
   code writing/review on Fable 5 ultracode/max. Flag a mismatch once before starting.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`; data: `make fetch cache`
  (Drive domains must be allowed; check `data/cache/` first — it sometimes survives).
  Notebook execution additionally needs `pip install nbformat nbclient ipykernel`.
- Commits: identity `Claude <noreply@anthropic.com>`; descriptive branch names, never
  `claude/...`; no PRs unless Lauren asks.
- Chat style for Lauren: answer first, short chunks, bold anchors, one next action
  (soul.md + preferences).
