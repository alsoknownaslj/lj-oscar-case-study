# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-11-02 (IDE-SQL session).**

## Where things stand

This repo, `alsoknownaslj/oscar-case-study-2`, is the project of record (split off
`alsoknownaslj/oscar-case-study` on 2026-11-01; pre-split history lives only there).
**No analysis or modeling has been done** and Lauren's 72-hour window is still NOT open.

New since the split: Lauren wants to run the project's SQL from a db extension in
VS Code, so the `make db` setup from `oscar-case-study` commit 48ddedb is ported here
(branch `vscode-sqltools-db`):

- `make db` → `scripts/build_db.py` writes a self-contained `data/oscar.duckdb`
  (base tables copied in, `sql/models/` views created inside, no file paths), at
  `storage_version 'v1.0.0'` so the SQLTools driver's bundled duckdb 1.3.2 can open it.
  Verified by opening with duckdb 1.3.2 and running every view.
- `sql/models/` now holds the four plumbing views (`stg_ccs`, `stg_claim_lines`,
  `stg_prescription_drugs`, `int_claim_lines_ccs`); `oscar_cs.db.connect()` loads them
  in layer order and `scripts/sql.py` uses it. The old repo's `dim_members`/`fct_*`
  models were deliberately NOT ported — they carry analysis framing, and framing here
  is still not pre-committed (see memory/decisions.md 2026-11-02).
- `.vscode/extensions.json` committed (recommendations only); SQLTools connection is
  added once via its UI — steps in CLAUDE.md under "Scripts & make targets".

## Next concrete step

Requirement 1 — the member health-status characterization:
1. Exclusions first, counted: claims rows with null/pre-2015 `date_svc`, junk codes
   (`stg_claim_lines` already flags these; 62 rows land `is_clean = false`).
2. Join claims→CCS via the normalized join (`int_claim_lines_ccs`; 99.89% row coverage
   reproduced on this container — report it).
3. Propose the characterization (not pre-committed): likely CCS level-2 condition flags
   with the chronic rule (≥2 claim dates ≥30 days apart) + light utilization stats;
   handle Residual/Symptoms chapters explicitly (`healthcare-claims` skill has the rules).
4. Sanity-check with 2–3 member vignettes, then a milestone summary to `reports/`.
Then requirement 2 (rx-only model): labels from claims/CCS, features from
`prescription_drugs` only. The guardrails are CLAUDE.md common mistakes 4–6 and 8;
mechanics come from `data:analyze` / `data:statistical-analysis`.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`
- A fresh clone has `ccs.csv` (committed) but NOT the two big CSVs: `make fetch`
  (Drive folder is link-shared; worked from this cloud environment on 2026-11-02),
  then `make cache`, then `make db` if browsing from an IDE. Cloud sessions need
  `drive.google.com` and `drive.usercontent.google.com` on the allowed domains.
- Container stack: Python 3.13, pandas 3.0.5, duckdb 2.0.0.
- Commits: identity `Claude <noreply@anthropic.com>`; work lands on descriptive
  branches (never `claude/...`), e.g. `vscode-sqltools-db`.
- `/fill-blanks`, `/retro`, `/remember` and the humanize hooks register only in sessions
  opened on this repo.
