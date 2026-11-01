# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-10-31 (setup session, closed cleanly).**

## Where things stand

Setup is 100% done and pushed to `main` (`alsoknownaslj/oscar-case-study`): data fetched
and verified, parquet cache + full profile, schemas reconciled in CLAUDE.md, all 11
fill-in questions answered (see `memory/preferences.md`), skills installed, zero open
blanks. **No analysis has been done yet** — the case study itself is untouched, and
Lauren's 72-hour window has NOT been opened.

## Next concrete step

Requirement 1 — the member health-status characterization:
1. Exclusions first, counted: claims rows with null/pre-2015 `date_svc`, junk codes.
2. Join claims→CCS via `normalize_icd10` (expect 99.89% row coverage; report it).
3. Propose the characterization (not pre-committed): likely CCS level-2 condition flags
   with the chronic rule (≥2 claim dates ≥30 days apart) + light utilization stats;
   handle Residual/Symptoms chapters explicitly (`healthcare-claims` skill has the rules).
4. Sanity-check with 2–3 member vignettes, then a milestone summary to `reports/`.
Then requirement 2 (rx-only model) per the `ml-classification` skill.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`
- A fresh clone has `ccs.csv` (committed) but NOT the two big CSVs: run `make fetch`
  (needs the Drive folder link-shared — Lauren may have flipped it back to Restricted
  after the 2026-10-31 fetch; ask her to re-share if fetch 403s), then `make cache`.
  The cloud environment already allowlists the two Drive domains.
- Commits: identity `Claude <noreply@anthropic.com>` (Lauren's stop-hook enforces it);
  push to `origin main` works (GitHub App installed).
- `/fill-blanks`, `/retro`, `/remember` register only in sessions opened on the repo.
