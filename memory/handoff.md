# Handoff — state of the project

_Rewrite this file whole (never append) at the end of a session or when direction changes.
It is the baton: the next session reads it before doing anything._

**As of 2026-11-01 (repo split-off session, closed cleanly).**

## Where things stand

This repo, `alsoknownaslj/oscar-case-study-2`, is the project of record now. It is a
full-history duplicate of `alsoknownaslj/oscar-case-study` (left untouched) with three
changes Lauren asked for on 2026-11-01:

- The repo-local `ml-classification` skill is gone. Generic DS mechanics — EDA, SQL,
  stats, viz, modeling — all come from Anthropic's `data` plugin; see the routing table
  in CLAUDE.md. `healthcare-claims` and `humanize` remain. There was no repo-local EDA
  skill to remove; EDA already routed to `data:explore-data`.
- The humanize pass is hook-enforced (`.claude/settings.json` + `.claude/hooks/`): the
  rule is injected at every session start/resume/clear/compact, and a nudge fires after
  each write to a human-facing `.md`. The hooks run in sessions opened on this repo.
- `memory/decisions.md` and `memory/preferences.md` record both calls.

Setup carried over intact: verified schemas in CLAUDE.md, profiled data dictionary,
`ccs.csv` committed, zero open blanks. **No analysis or modeling has been done** (none
existed to carry over or strip), and Lauren's 72-hour window is still NOT open.

## Next concrete step

Requirement 1 — the member health-status characterization:
1. Exclusions first, counted: claims rows with null/pre-2015 `date_svc`, junk codes.
2. Join claims→CCS via `normalize_icd10` (expect 99.89% row coverage; report it).
3. Propose the characterization (not pre-committed): likely CCS level-2 condition flags
   with the chronic rule (≥2 claim dates ≥30 days apart) + light utilization stats;
   handle Residual/Symptoms chapters explicitly (`healthcare-claims` skill has the rules).
4. Sanity-check with 2–3 member vignettes, then a milestone summary to `reports/`.
Then requirement 2 (rx-only model): labels from claims/CCS, features from
`prescription_drugs` only. The guardrails are CLAUDE.md common mistakes 4–6 and 8;
mechanics come from `data:analyze` / `data:statistical-analysis`.

## Fresh-container notes

- `pip install -r requirements.txt && pip install -e .`
- A fresh clone has `ccs.csv` (committed) but NOT the two big CSVs: run `make fetch`
  (needs the Drive folder link-shared — ask Lauren to re-share if it 403s), then
  `make cache`. Cloud sessions need `drive.google.com` and `drive.usercontent.google.com`
  on the environment's allowed domains (the original environment has both).
- Commits: identity `Claude <noreply@anthropic.com>`; push to `origin main` of
  `alsoknownaslj/oscar-case-study-2` works (verified 2026-11-01).
- `/fill-blanks`, `/retro`, `/remember` and the humanize hooks register only in sessions
  opened on this repo.
