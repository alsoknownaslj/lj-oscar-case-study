# Oscar DS Case Study

My working repo for the Oscar Health data science case study. The task has two parts.
First, characterize each member's health status from their outpatient claims, using CCS
(Clinical Classifications Software) diagnosis categories. Second, predict that status
from prescription drug data alone. The data simulates about 200k members over 3 years,
in three base tables. The full brief is in [`references/case-study.md`](references/case-study.md).

## Status

The case study is done (2026-11-02). Start with the final report.

- Part 1: each member is a set of CCS conditions, and each condition is tagged
  one-off, episode or chronic from its claim dates. About 15% of the 245,151 members
  with claims have at least one chronic condition.
- Part 2: I fit one logistic regression per condition on drug fills only. AUROC (area
  under the ROC curve) runs 0.80 to 0.97, and the flagged lists are 8 to 41 times more
  precise than random picks.

<!-- AUTO:reports:BEGIN -->
- [`2026-11-02_case-study-report.md`](reports/2026-11-02_case-study-report.md): Classifying member health status from medical and prescription drug usage ([PDF](reports/2026-11-02_case-study-report.pdf))
- [`2026-11-02_eda-session.md`](reports/2026-11-02_eda-session.md): EDA before the definition: what two days of exploration established
- [`notebooks/01_final_report.ipynb`](notebooks/01_final_report.ipynb): Final report — supporting notebook
<!-- AUTO:reports:END -->

## Reproducing the results

```bash
pip install -r requirements.txt
pip install -e .
make fetch cache                        # data from Google Drive, then the parquet cache
python scripts/build_health_status.py   # part 1 (about 11s)
python scripts/build_rx_model.py        # part 2 (about 16s)
python scripts/report_figures.py        # report figures
```

The notebook `notebooks/01_final_report.ipynb` reproduces every number in the report.
Running it headless also needs `pip install nbformat nbclient ipykernel`.

### Getting the data

The three CSVs (447 MB together) live in the project's
[Google Drive folder](https://drive.google.com/drive/u/0/folders/1h4W_vrdIimrIQsGILMqhxTaatpzukWzU).
`make fetch` downloads them into `data/raw/` once the folder is shared by link. A cloud
session also needs `drive.google.com` and `drive.usercontent.google.com` on its allowed
domains. You can also download `claim_lines.csv`, `prescription_drugs.csv` and `ccs.csv`
by hand into `data/raw/`.

`claim_lines.csv` (65 MB) and `prescription_drugs.csv` (371 MB) stay out of git because
of GitHub's 100 MB file limit. `ccs.csv` (11 MB) is committed.

### Make targets

<!-- AUTO:make:BEGIN -->
| Command | Does |
|---|---|
| `make fetch` | download the 3 datasets (+ brief PDF) from Google Drive into data/raw/ |
| `make cache` | build faithful all-string parquet mirrors in data/cache/ |
| `make profile` | profile raw tables and rewrite the AUTO section of the data dictionary |
| `make db` | build self-contained data/oscar.duckdb (tables + model views) for IDE browsing |
| `make readme` | regenerate the AUTO sections of README.md |
| `make lint` | format + lint python |
| `make sql-check` | lint saved SQL |
| `make test` | run pytest (includes the README-in-sync check) |
<!-- AUTO:make:END -->

### Scripts

<!-- AUTO:scripts:BEGIN -->
| Script | What it does |
|---|---|
| `scripts/build_cache.py` | Build faithful parquet mirrors of the raw CSVs in data/cache/ |
| `scripts/build_db.py` | Materialize data/oscar.duckdb: a self-contained database for IDE browsing |
| `scripts/build_health_status.py` | Build the requirement-1 health-status characterization (v2) from claims + CCS |
| `scripts/build_rx_model.py` | Requirement 2 — infer health status from prescription drug data alone |
| `scripts/check_utilization_baseline.py` | Ablation: how much of the rx model is just "sick members fill more prescriptions"? |
| `scripts/fetch_data.py` | Download the case-study files from Google Drive into data/raw/ |
| `scripts/profile_data.py` | Profile the raw tables and rewrite the AUTO section of references/data-dictionary.md |
| `scripts/report_figures.py` | Render the figures for the final case-study report (health status v2) |
| `scripts/sql.py` | Run duckdb SQL against the project tables and models |
| `scripts/update_readme.py` | Regenerate the AUTO sections of README.md from the files they describe |
| `scripts/eda/` (15 scripts) | exploratory analysis behind the EDA report |
<!-- AUTO:scripts:END -->

## How the repo works with Claude

The repo is set up for Claude Code sessions to work in over time, with me steering.

- `CLAUDE.md` is the agent's operating manual: the case study, table schemas, known
  data pitfalls, report shape and skill routing. Claude reads it automatically.
- `soul.md` describes how the agent works with me: evidence habits and voice.
- `memory/` holds what sessions learn: data quirks, lessons, decisions, my
  preferences and a handoff note. Every session loads it.
- `references/` is standing knowledge: the brief, data dictionary, domain notes,
  metrics definitions and report style.
- `.claude/` holds the project skills (`humanize`, `healthcare-claims`), the hooks and
  the slash commands below. EDA, SQL, stats and viz come from Anthropic's `data` plugin.

<!-- AUTO:commands:BEGIN -->
- `/fill-blanks`: Walk Lauren through the remaining FILL-IN blanks, one at a time
- `/remember`: File one fact into the right memory file
- `/retro`: End-of-session retrospective — distill what happened into memory/ and surface open blanks
<!-- AUTO:commands:END -->

Two hooks run in every session. One reminds Claude to run `humanize` on any prose I'll
read. The other keeps this README current: after each file change it regenerates the
sections between the `AUTO` markers, and it asks Claude to recheck the hand-written
sections when the files behind them change. Run `make readme` to regenerate by hand.
`make test` fails if the generated sections are stale.

## Layout

```
CLAUDE.md, soul.md   agent operating manual and working style (start here)
data/                raw/ (immutable), cache/, processed/ (mostly gitignored)
references/          brief, data dictionary, domain and metrics notes, report style
memory/              handoff, learnings, data quirks, decisions, preferences
scripts/             data setup, the two pipelines, figures, SQL runner, eda/
src/oscar_cs/        loaders, code normalization, health-status rules, paths
sql/                 saved duckdb queries and models/ (views behind make db)
notebooks/           the notebook that reproduces the report
reports/             dated write-ups and figures (the deliverables)
tests/               unit and smoke tests
```

## Credits

The `humanize` skill is vendored from [blader/humanizer](https://github.com/blader/humanizer)
(MIT). See `.claude/skills/humanize/ATTRIBUTION.md`.
