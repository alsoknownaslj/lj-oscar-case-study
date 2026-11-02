# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-11-02 (two-day EDA session with Lauren; merged to main together with the
parallel soul.md/IDE-SQL session).**

## Where things stand

Lauren reopened the requirement-1 framing before ratifying it and ran a collaborative
EDA-first pass instead. Everything from both days is on `main`, merged with a parallel
session's work (see below).

- **The findings home is `reports/2026-11-02_eda-session.md`** (humanized, 8 findings,
  2 logged decisions, next-session agenda). Every number reproduces from
  `scripts/eda/*.py`; all session figures are in `reports/figures/` under the
  `2026-11-02_eda-session_` prefix. `memory/data-quirks.md` was compacted to a digest
  that points there.
- **Decisions in force:** canonical analysis window **[2015-09-01, 2018-06-04]**
  (`ANALYSIS_WINDOW_*` in `src/oscar_cs/health_status.py`); median and quartile tier
  binning rejected. **Pending Lauren:** the outlier policy (percentile fences, >p99
  high-utilizer flag, remove nobody) and the whole health-status definition.
- **The requirement-1 draft still exists** (pipeline `scripts/build_health_status.py`,
  report `reports/2026-11-01_health-status-characterization.md`) but its framing is
  explicitly reopened and its numbers predate the canonical window — a prototype to
  rebuild once the definition lands, not the baseline.
- **Merged from the parallel session (same days, main):** `soul.md` at the repo root —
  the analyst persona, named **Ada** (chat only; commit identity unchanged), auto-imported
  by CLAUDE.md which wins on conflict; `references/metrics-dictionary.md`; `make db`
  (self-contained `data/oscar.duckdb` for SQLTools review) with `sql/models/` staging
  views and `oscar_cs.db.connect(models=True)`. Our `connect_views()`/`read_sql()` now
  live in the same module. That session's "no analysis has been done" notes are
  superseded by this handoff. Note: `sql/models/` staging views predate the canonical
  window — align them when the definition lands.
- The old `req1-health-status` branch is merged; cloud sessions cannot delete remote
  branches (403), so Lauren can remove it in the GitHub UI if she wants it gone.

## Next session agenda (Lauren's words, 2026-11-02)

1. **Bins:** design non-arbitrary low/med/high bins for diagnostic-claim volume, fill
   volume, and the claims×rx contingency table. Median splits (empty mid bin) and
   quartiles (ties collapse: the median pair is a single touch) are out. Candidates to
   evaluate: log-scale natural breaks, mixture models, clinically anchored cuts.
2. **Reconvene the health-status definition** with the evidence stacked (details in the
   EDA report): repetition shapes support chronic/episode/one-off; the draft chronic
   rule decomposes 44% arc / 39% recurrent / 16% continuous; "recurrent" needs rx
   corroboration or category priors (reinfection trap); psych chronicity lives in rx,
   not claims; immunizations/screening has five independent strikes against being a
   condition; the symptom-only tier question is open; rx sustained-therapy (≥3 fills
   ≥90d) is the natural rx-side chronicity flag.
3. **Requirement 2** follows: labels from the ratified definition; 37,583 in-window
   rx-only members are the scoring population; the no-fill ranking is the empirical
   predictability map. Guardrails stay CLAUDE.md mistakes 4–6 and 8.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`; data: `make fetch cache`
  (needs the two Drive domains allowed; the parquet cache sometimes survives a container
  pause while raw CSVs do not — `connect_views` prefers the cache, so check
  `data/cache/` before re-fetching).
- Commits: identity `Claude <noreply@anthropic.com>`; branch names descriptive, never
  `claude/...`; no PRs unless Lauren asks.
- Chat style for Lauren: answers first, short chunks, bold anchors, one clear next
  action — full detail in `soul.md` and preferences (2026-11-02 entries).
- The 72-hour case-study window is Lauren's to track; requirement-2 modeling has not
  started.
