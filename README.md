# Oscar DS Case Study

Working repo for the Oscar Health data science case study: **characterize member health
status from medical claims (via CCS categories), then predict it from prescription drug
data alone.** ~200k simulated members, 3 years of utilization, three base tables.

The full brief is in [`references/case-study.md`](references/case-study.md).

## This is an agentic repo

It's built to be worked on by Claude Code sessions over time, with Lauren steering:

- **`CLAUDE.md`** — the agent operating manual: case study, table schemas, known pitfalls,
  report shape, skill routing. Read it first (Claude does automatically).
- **`memory/`** — self-learning: data quirks, lessons, decisions, preferences. Auto-imported
  into every session; updated as work happens (`/remember`, `/retro`).
- **`references/`** — standing knowledge as markdown: brief, data dictionary, domain notes,
  report style.
- **`.claude/`** — project skills (`humanize`, `healthcare-claims`), slash commands
  (`/retro`, `/remember`, `/fill-blanks`), and plugin wiring (Anthropic's `data` plugin
  for EDA/SQL/stats/viz/ML).
- **`scripts/`** — repeatable mechanics: fetch data, build parquet cache, profile tables,
  run SQL.

Open questions for Lauren are marked `FILL-IN` (`grep -rn "FILL-IN" .`).

## Setup

```bash
pip install -r requirements.txt
pip install -e .
```

### Getting the data (not committed — 447 MB)

The three CSVs live in the project's
[Google Drive folder](https://drive.google.com/drive/u/0/folders/1h4W_vrdIimrIQsGILMqhxTaatpzukWzU)
under `data/`. Either:

1. Set that Drive folder to "anyone with link can view", then `python scripts/fetch_data.py`; or
2. Download `claim_lines.csv`, `prescription_drugs.csv`, `ccs.csv` by hand into `data/raw/`.

Then:

```bash
make cache    # typed parquet mirrors (fast loads)
make profile  # auto-fills references/data-dictionary.md
```

`claim_lines.csv` (65 MB) and `prescription_drugs.csv` (371 MB) stay out of git
(GitHub's 100 MB file limit); `ccs.csv` (11 MB) is committed once fetched.

## Layout

```
CLAUDE.md            agent operating manual (start here)
data/   raw/ cache/ processed/        (raw is immutable; most of it gitignored)
references/          brief, data dictionary, domain notes, report style, samples
memory/              learnings, data-quirks, decisions, preferences
scripts/             fetch_data, build_cache, profile_data, sql runner
src/oscar_cs/        loaders, code normalization, paths
sql/                 saved duckdb queries
notebooks/           numbered exploration notebooks
reports/             dated write-ups + figures (the deliverables)
tests/               smoke tests
```

## Credits

The `humanize` skill is vendored from [blader/humanizer](https://github.com/blader/humanizer)
(MIT) — see `.claude/skills/humanize/ATTRIBUTION.md`.
