# Oscar DS Case Study — Agent Manual

This is the operating manual for any Claude session working in this repo. Read it as the
contract. Lauren (laurenjackson1028@gmail.com) owns the project; you are her analyst pair.
Open blanks are marked `FILL-IN` — they are hers to answer, not yours to invent. Run
`/fill-blanks` when she's around; never silently fabricate an answer to one.

This manual says what to do. Who you are while doing it — stance, evidence habits,
voice — lives in the soul file (auto-imported; CLAUDE.md wins on any conflict):

@soul.md

## The case study

Oscar Health data science case study: **classify member health status from medical and
prescription drug usage**. Full brief: `references/case-study.md` (verbatim from the PDF in
the Drive folder). The two requirements, in order:

1. **Characterize each member's health status from their outpatient claims**, using the
   CCS diagnosis-category mapping. A useful, robust, high-level description ("member xyz
   had cancer and a broken leg") beats a clever one.
2. **Infer that same status from prescription drug data alone** — a simple model that could
   be applied to new members' drug data to predict their status. If a full model isn't
   feasible in the time, a well-argued plan + what the data shows is acceptable.

Context that shapes every decision:
- Data simulates **200,000 members over 3 years**. It is synthetic — no real PHI — but
  handle it with real-PHI habits anyway (no member-level rows in committed reports).
- The brief estimates **~4 hours of work within a 72-hour window**. Favor clear, defensible
  prototypes and honest limitations over polish. Creative framing is explicitly welcomed.
- The audience evaluates how quickly a problem + dataset is understood and prototyped.

Status (Lauren, updated 2026-11-02): the 72-hour window is **open, deadline 5pm on
2026-11-02 (Lauren's local time)**; this replaced the 2026-10-31 "not started" status.
**No framing is pre-committed**: the definition of "health status" gets proposed and justified during the
analysis itself. Deliverables are **private, for Oscar reviewers only**.

## Data status — read this first

**Status: COMPLETE (2026-10-31) — all three raw files + brief PDF downloaded byte-exact,
parquet cache built in `data/cache/`, full profile written.** Update this line if the data
setup changes.

- Fresh clone? `make fetch cache profile`. Fetching needs the
  [Drive folder](https://drive.google.com/drive/u/0/folders/1h4W_vrdIimrIQsGILMqhxTaatpzukWzU)
  link-shared; a cloud session additionally needs `drive.google.com` and
  `drive.usercontent.google.com` on the environment's allowed domains. `fetch_data.py`
  downloads with curl against `drive.usercontent.google.com` directly — bare gdown fails on
  restricted networks (it bounces via `doc-XX-docs.googleusercontent.com` mirrors).
- In git: `ccs.csv` (11 MB) yes; `claim_lines.csv` / `prescription_drugs.csv` never
  (GitHub 100 MB limit) — rebuild locally instead.
- Exact per-column numbers: `references/data-dictionary.md` (AUTO section regenerates via
  `make profile`).

## Base tables

All raw files belong in `data/raw/` and are **immutable** — never edit, re-sort, or
overwrite a raw file; derive into `data/cache/` (faithful parquet) or `data/processed/`.

### `ccs.csv` — ICD-10 → clinical category mapping (10.9 MB, 72,167 rows) ✓ verified

| column | type | notes |
|---|---|---|
| `diag` | str | ICD-10-CM code, **no dot**, 3–7 chars, **unique** — safe join key |
| `diag_desc` | str | code description |
| `ccs_1_desc` | str | level 1 — 18 chapters |
| `ccs_2_desc` | str | level 2 — 135 real values + a filler; **a single space `' '` (not `''`!) for the 7,621 Residual-chapter codes** — strip before testing blankness; ~44% embed a code like `[135.]` |
| `ccs_3_desc` | str | level 3 — 281 values, never blank; often repeats level 2 |

No true nulls. `src/oscar_cs/data.py::parse_ccs2_code` extracts the bracket codes.

### `claim_lines.csv` — diagnoses on medical claims (65 MB, 1,919,983 rows) ✓ verified

One row = one diagnosis × member × day. Columns: `record_id` (unique int 1…1,919,983),
`member_id` (str, `M0000001`-style, **245,166 distinct**), `date_svc` (date — **24 nulls,
38 dirty rows back to 1899**; real window **2015-09 → 2018-05** (Jan–Aug 2015 holds only
~160 rows; ramps from 2015-09, peaks 2016, tapers out Apr–May 2018; the 2018-12-06 max is
**6 stray rows** after 2018-06-04)),
`diag1` (ICD-10, **91.9% dotted** e.g. `N92.6`; junk includes 63× `000` and one quoted
comma code `"L02.,821"`). The file has quoted fields deep inside — every reader must set
`quote='"'` (auto-sniffing sees none in the first 20k rows and breaks at row 1,783,434).

### `prescription_drugs.csv` — filled prescriptions (371 MB, 3,005,934 rows) ✓ verified

One row = one fill. Columns: `record_id` (unique, up to 19 digits — keep as str, never
float), `member_id` (**240,735 distinct**), `date_svc` (**2013-12 → 2018-06** — starts
~21 months before claims coverage; both tables taper out together over Apr–May 2018),
`ndc` (str, all 11-digit, leading
zeros real: `00002143301`), plus the feature hierarchy `drug_category` (**92**) →
`drug_group` (**464**) → `drug_class` (**687**); 20,368 distinct NDCs (all counts
exact-verified — the profiler's distinct column is approximate). Query via duckdb or the
parquet cache, never repeated raw `pd.read_csv`.

### How the tables relate

```
claim_lines ──(normalize_icd10(diag1) = ccs.diag)──> ccs    # 99.89% of rows map; 217 codes don't
claim_lines ──(member_id)──> prescription_drugs             # 194,290 members in BOTH tables
                                                            # (245,166 claims / 240,735 rx)
```

Loading rules (enforced by `src/oscar_cs/data.py` — use it, don't hand-roll readers):
- **Every code column loads as string.** Never let pandas infer ints for `diag` or NDC.
- Parquet cache first (`data/cache/`), raw CSV fallback.
- Heavy aggregation goes through duckdb (`scripts/sql.py`, views over the tables).

## Common mistakes to avoid with this dataset

1. **Joining ICD-10 codes without normalizing format.** `ccs.diag` is undotted; **91.9% of
   `claim_lines.diag1` are dotted** (verified). Always join on `normalize_icd10()` (strip
   dots/whitespace, uppercase) — that takes row coverage to **99.89%**. Report the coverage
   % every time — never a silent inner join.
2. **Dropping unmapped diagnosis codes silently.** **217 distinct claim codes (0.11% of
   rows)** have no CCS row, junk like `000` included. Decide explicitly what happens to
   them and say so in the report.
3. **Reading codes as numbers.** NDCs have leading zeros; some code columns can collapse
   to scientific notation. Everything code-like is `str` — this is why `build_cache.py`
   forces all-varchar.
4. **Leaking members across the train/test split.** Requirement 2 predicts status for
   *additional members*. Split by `member_id`, never by row; a member's rows must never
   straddle the split.
5. **Letting claims features leak into the rx-only model.** The model's inputs must be
   derivable from `prescription_drugs` alone. Claims/CCS may only define the *labels*.
6. **Treating "health status" as single-label.** Members have multiple conditions
   simultaneously — multi-label (or per-condition one-vs-rest) framing is the natural fit.
   Expect heavy class imbalance; accuracy is a useless headline metric here (prefer
   per-class AUROC/AUPRC — `data:statistical-analysis` has the mechanics).
7. **Choosing the wrong CCS granularity.** Level 1 (18 chapters) may be too coarse to be
   useful; level 3 too sparse. Justify the level you characterize members at; parse the
   level-2 bracket codes rather than string-matching long descriptions.
8. **Ignoring the time dimension.** Rx starts 2013-12 but claims only 2015-09 (10.4% of
   fills are claims-blind), and BOTH feeds taper out over Apr–May 2018 — the "claims to
   2018-12" tail is 6 stray rows. Cross-table and population stats use the canonical
   window **2015-09-01 → 2018-06-04** (`ANALYSIS_WINDOW_*` in
   `src/oscar_cs/health_status.py`); treat Apr–May 2018 as partial coverage for
   recency-sensitive measures, and state the observation window for labels vs. features
   (same-period inference and prospective prediction are different claims and splits).
9. **Row-counting instead of member-counting.** Utilization tables are long; "X% of rows"
   and "X% of members" diverge wildly. Default denominators to members unless stated.
10. **Pandas 3.0 surprises.** This repo pins pandas ≥ 3: strings are `str` dtype by
    default and copy-on-write is always on. Don't write pandas-2-era chained assignment.
11. **Trusting the files to be clean.** They're dirty on purpose: `date_svc` nulls and
    1899-sentinel dates in claims, junk diagnosis codes, a quoted comma-embedded code.
    Filter with explicit, counted exclusions, and parse CSVs with `quote='"'`.
12. **Trusting `approx_count_distinct`.** duckdb's approximation made genuinely unique
    keys (`ccs.diag`, both `record_id`s) look duplicated. Verify keys with exact
    `count(distinct …)` before claiming anything about them.

Lauren (2026-10-31): no further known gotchas beyond the documented ones — standing stance
is **stay alert**: treat anything weird as potentially intentional, verify it, and log it
in `memory/data-quirks.md` the moment it's confirmed.

## Reports — how to shape them

Write-ups live in `reports/` as `YYYY-MM-DD_slug.md` (figures in `reports/figures/`,
referenced relatively). Default skeleton (details + taste: `references/report-style.md`):

1. **TL;DR** — 3–5 sentences, findings first, numbers included.
2. **Approach & why** — framing decisions and what was ruled out, briefly.
3. **Findings** — each one: claim → evidence (number/figure) → so-what.
4. **Model** (when applicable) — setup, metrics with baselines, calibration, limitations.
5. **What more time buys** — ranked, scoped next steps (the brief explicitly invites this).
6. **Open questions** — what the data can't answer; what you'd ask Oscar's team.
7. **Appendix** — reproduction pointers (script/notebook paths), data caveats.

Hard rules: every figure follows the `dataviz` skill; every number traceable to a script or
notebook committed in the same state; member-level rows never appear in a report. **Every
report gets a `humanize` pass before it's called done** — Lauren's reports should sound
like Lauren, not like a model. This is hook-enforced: `.claude/hooks/` injects the rule at
every session start and nudges after every prose write (`.claude/settings.json`).

Lauren's calls (2026-10-31): audience = **Oscar reviewers, private**. Format of record =
**markdown report + supporting notebook** (the report is what gets read; the notebook
reproduces every number). Voice = **first person, plain and direct**. Length = **~2 pages
+ appendix**. Sections 5 and 6 above are mandatory in every report. Figures = matplotlib
with the **seaborn look** (`sns.set_theme()`), static PNGs.

## Skills — routing table

| Situation | Use |
|---|---|
| First look at a table, null/dupe hunting | `data:explore-data` |
| Writing/optimizing SQL (duckdb here) | `data:sql-queries` + `.sqlfluff` config |
| Stats rigor (tests, distributions, outliers) | `data:statistical-analysis` |
| Any chart, figure, or dashboard | `dataviz` (style) + `data:create-viz` / `data:build-dashboard` |
| QA before sharing an analysis | `data:validate-data` |
| ICD-10 / CCS / NDC semantics, claims logic | `healthcare-claims` (this repo) |
| Framing, training, evaluating the classifier | `data:analyze` + `data:statistical-analysis` |
| Any prose a human will read | `humanize` (this repo) — final pass, always |
| Code got sprawly | `simplify` (built-in), then `code-review` before big merges |

All generic DS mechanics — EDA, SQL, stats, viz, and modeling — come from Anthropic's
`data` plugin (Lauren, 2026-11-01: the repo-local `ml-classification` skill was retired
when this repo split off from `oscar-case-study`). The one repo-local DS skill,
`healthcare-claims`, adds case-study-specific judgment only. Don't install additional
EDA/ML skills without checking for overlap with this table.

## Memory & self-learning protocol

The four memory files below are auto-imported into every session. They are the project's
accumulated brain — **trust them over your priors, and keep them current.**

- When you discover a durable fact about the *data* → append to `memory/data-quirks.md`.
- When an approach works/fails, or a tool lesson → `memory/learnings.md`.
- When a decision with alternatives gets made → `memory/decisions.md` (what, why, what was
  rejected). Never re-litigate a logged decision unless Lauren reopens it.
- When Lauren expresses a preference (style, tools, cadence) → `memory/preferences.md`.
- `memory/handoff.md` is the baton between sessions: a short state-of-the-project note.
  Rewrite it whole (never append) at session end or whenever direction changes.

Write entries at the moment of discovery, dated, one line of context minimum. At the end of
a working session, run `/retro` to sweep anything missed. `/remember <fact>` files a single
entry fast. Keep each file under ~150 lines; compact stale entries rather than deleting
history (move detail to `references/` if it grows).

@memory/handoff.md
@memory/learnings.md
@memory/data-quirks.md
@memory/decisions.md
@memory/preferences.md

## Scripts & make targets

| Command | Does |
|---|---|
| `python scripts/fetch_data.py` | pulls the 3 CSVs (+ case-study PDF) from Drive into `data/raw/` |
| `make cache` | faithful all-string parquet mirrors → `data/cache/` |
| `make profile` | profiles raw data → rewrites AUTO section of `references/data-dictionary.md` |
| `python scripts/sql.py "<query>" ` / `-f sql/x.sql` | duckdb with views over the tables |
| `make db` | self-contained `data/oscar.duckdb` (tables + model views) for IDE browsing |
| `make lint` / `make test` | ruff (format+check) / pytest |

Scripts are the memory of *how*; if you do a manual data step twice, promote it to a script.

SQL from the IDE: run `make db`, install the recommended extensions
(`.vscode/extensions.json`: SQLTools + the DuckDB driver), then add a SQLTools
connection once via its UI (driver DuckDB, database file `data/oscar.duckdb`, access
mode Read Only; the driver doesn't resolve `${workspaceFolder}`, so a committed
connection can't be portable). Rebuild with `make db` after editing `sql/models/` and
reconnect in the IDE; duckdb allows one writer, so a read/write IDE connection blocks
the rebuild.

## References index

| File | What's in it |
|---|---|
| `references/case-study.md` | the full brief, verbatim + source links |
| `references/data-dictionary.md` | per-table schemas; AUTO section rewritten by `make profile` |
| `references/report-style.md` | report shaping details + Lauren's preferences (FILL-INs live here) |
| `references/domain-notes.md` | ICD-10 / CCS / NDC primer, drug→condition inference notes |
| `references/metrics-dictionary.md` | plain definitions of statistical concepts reports lean on (acronyms spelled out once; unsure whether a concept belongs → ask Lauren) |
| `references/samples/ccs_sample.csv` | real 400-row head of `ccs.csv` |

New standing knowledge gets a new md file here + a row in this table. Session-specific
output goes to `reports/` or `notebooks/`, not here.

## Conventions

- **Python:** ruff is the law (`make lint`); line length 100; type hints on `src/` functions;
  notebooks are for exploration, anything load-bearing graduates to `src/` or `scripts/`.
- **SQL:** duckdb dialect, sqlfluff-formatted, lowercase keywords ok but be consistent;
  queries that matter live in `sql/`, not inline strings.
- **Notebooks:** `notebooks/NN_topic.ipynb`, restart-and-run-all before committing.
- **Git:** small commits, imperative subjects, body explains *why*. Never commit
  `claim_lines.csv` or `prescription_drugs.csv` (GitHub 100 MB limit — `.gitignore`
  enforces); `ccs.csv` is allowed once fetched.
- **Branches (must):** a branch name never includes `claude/` and always says what the
  work is (`req1-health-status`, `rx-model-baseline`) — never autogenerated nonsense
  words. If a session is handed a `claude/...` branch, do the work on a properly named
  branch instead.
- **PRs (must):** descriptions carry no "Generated with Claude Code" footer.
  `attribution.pr` is blanked in `.claude/settings.json`; sessions writing PR bodies by
  hand don't append it either.
- **Paths:** always via `src/oscar_cs/paths.py`; no absolute paths in committed code.
- Blanks: grep-able with `grep -rn "FILL-IN" CLAUDE.md references/ memory/`.
