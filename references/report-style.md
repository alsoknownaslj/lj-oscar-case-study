# Report style — how write-ups should be shaped

The skeleton lives in `CLAUDE.md` ("Reports"); this file holds the detail and Lauren's
preferences (all current ones answered 2026-10-31). When a new preference question comes
up, add it here as a `FILL-IN` block and collect it with `/fill-blanks`.

## Defaults (apply until Lauren overrides)

- **Findings before methods.** The first screen of any report answers "what did we learn,
  with numbers". Nobody should scroll to find the point.
- **One claim per paragraph**, each backed by a number, table, or figure produced by
  committed code. If a number can't be traced to a script/notebook, it doesn't ship.
- **Figures** follow the `dataviz` skill (titles that state the takeaway, labeled axes,
  readable at phone width, no unlabeled dual axes). Save to `reports/figures/` as
  `YYYY-MM-DD_slug_fig01.png`, referenced relatively.
- **Tables** are for ≤ ~10 rows of enumerable facts; distributions become figures.
- **Denominators are explicit** — "12% of members (24,031 of 200k)", never a bare "12%".
- **Limitations are a first-class section**, not a disclaimer sentence. Synthetic data,
  unmapped codes, censoring, label noise — say what would break in production.
- **Voice:** plain language, short sentences, no hedging filler, define each acronym once.
  Final pass through the `humanize` skill is mandatory before a report is "done".
- **Member privacy habits** even on synthetic data: no raw member-level rows in reports;
  aggregate or use invented illustrative examples labeled as such.

## Case-study deliverable (requirement-specific)

- The brief wants **code + some output** and rewards fast understanding + prototyping.
  Target a deliverable the reviewer can absorb in ~10 minutes.
- Show the health-status characterization with 2–3 concrete member vignettes
  ("member 12345: diabetes + hypertension, 14 claims over 2 years") — aggregated stats
  alone don't demonstrate it works.
- Model section must include: label definition, features (rx-only), split design
  (by member), baseline comparison, per-class metrics, and what you'd do with more time.

## Lauren's preferences (decided 2026-10-31)

- **Audience:** Oscar reviewers only — repo and deliverables stay private.
- **Format of record:** markdown report (`reports/YYYY-MM-DD_slug.md`) + a supporting
  notebook that reproduces every number. The report is the artifact reviewers read.
- **Voice:** first person, plain and direct ("I grouped members by…"). The `humanize` pass
  stays mandatory.
- **Length:** ~2 pages for the main report; everything else goes to the appendix/notebook.
- **Standing sections:** "What more time buys" (ranked) and "Open questions" appear in
  every report, before the appendix. No time-spent accounting, no AI-assistance note.
- **Figures:** matplotlib with the seaborn look (`sns.set_theme()`), static PNGs; the
  `dataviz` skill's rules still apply on top.
- **Code:** clear and tidy, not production — ruff-clean and readable beats typed/tested.
- **Session summaries:** at milestones only (characterization done, model v1, …), not per
  session.

Log every newly answered preference in `memory/preferences.md` too, so it survives even if
this file is restructured.
