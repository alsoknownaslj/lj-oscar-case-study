# Data quirks — durable facts about the dataset

Append as discovered (newest last). Every entry: fact + how it was verified.

- **2026-10-31** — `ccs.diag` is **undotted** ICD-10-CM (`A000`, `A0100`), 3–7 chars.
  Verified on a real 6,572-row head. The brief says claim-line formatting differs ⇒ expect
  dotted codes there (**verify on first load**, direction matters for `normalize_icd10`).
- **2026-10-31** — `ccs_2_desc` embeds numeric CCS ids in brackets for ~44% of sampled rows
  (`Intestinal infection [135.]`); the rest have no bracket id. Parse with
  `parse_ccs2_code()`, don't regex ad hoc in notebooks.
- **2026-10-31** — All 18 CCS level-1 chapters present, including the junk-drawer
  "Residual codes; unclassified; all E codes [259. and 260.]" — characterization must
  handle it explicitly (likely exclude from "conditions", keep as a data-quality note).
- **2026-10-31** — CCS description fields use **semicolons in place of commas**
  ("Endocrine; nutritional; and metabolic diseases...") — never split these on `;`, and
  quote properly when exporting CSVs.
- **2026-10-31** — File inventory (bytes, Drive mtime 2018-05-16): claim_lines 65,345,631;
  prescription_drugs 371,337,198; ccs 10,904,504. Simulated data for 200k members / 3 yrs
  per the brief — confirm actual member counts and date ranges at first profile.
- **2026-10-31 (full data verified)** — Real schemas: claims = `record_id, member_id,
  date_svc, diag1` (1,919,983 rows, record_id unique); rx = `record_id, member_id,
  date_svc, ndc, drug_category, drug_group, drug_class` (3,005,934 rows; record_id =
  19-digit ints — string, never float). `diag1` 91.9% dotted; normalized join → 99.89% CCS
  row coverage, 217 distinct codes unmapped.
- **2026-10-31** — Dirty-by-design values in claims: 24 null `date_svc` + ~37 rows dated
  1899–2014 (sentinels/strays); 63 rows of diag `000`; one `"L02.,821"` comma code at row
  1,783,434 — which also means **the CSV has quoted fields: always parse with
  `quote='"'`** (duckdb's sniffer sees no quotes in the first 20k rows and errors).
- **2026-10-31** — Window mismatch: claims 2015-12 → 2018-12 (peak 2016); rx 2013-12 →
  2018-06. Members: 245,166 claims / 240,735 rx / **194,290 in both**; the brief's
  "200,000 members" is nominal. ~51k claims-only + ~46k rx-only members exist and need an
  explicit story in any analysis.
- **2026-10-31** — `ccs_2_desc` is blank (empty string, not null) for exactly the 7,621
  Residual-chapter codes; `ccs_3_desc` never blank; `diag` unique. NDC: all 11-digit,
  leading zeros intact.
- **2026-11-01** — Claims window correction: volume ramps from **2015-09**, not 2015-12
  (monthly counts: Jan–Aug 2015 total ≈163 rows, Sep 6,365 → Oct 18,895 → Nov 26,906 →
  Dec 35,647; peak 2016). CLAUDE.md + dictionary updated. Verified via duckdb monthly counts.
- **2026-11-01** — Exact cleaning numbers: 24 null dates + **38** pre-2015 rows (docs said
  ~37) = 62 excluded; exactly **one member** (M0061560, single claim dated 2014-08-08)
  drops out — and they have 11 rx fills, so the both-tables overlap reads **194,289**
  after cleaning vs the documented raw 194,290.
- **2026-11-01** — Top unmapped codes (after cleaning): `99999` **1,561 rows**, `KHDX`
  103, `000` 61 (63 raw; 2 of the 63 also carry null/pre-window dates). 217 distinct
  unmapped codes confirmed exactly. `99999`/`KHDX` were previously undocumented.
- **2026-11-01** — Profiling trap confirmed with numbers: the Symptoms/Z-code chapter is
  18.1% of kept claim rows, and its "Factors influencing health care" category alone
  touches **53.9% of members** — left in, it would be the #1 "condition" (2× respiratory
  infections). Residual chapter: 1.6% of rows. Both bucketed out of condition flags.
- **2026-11-02** — Correction: Residual-chapter `ccs_2_desc` is a **single space `' '`**,
  not an empty string — `nullif(x, '')` and `== ''` miss it; strip/trim first. (Yesterday's
  pipeline bucketed by chapter name, so unaffected.) No level-2 name spans two chapters;
  Residual has no level 2 but **22 level-3 categories** (level 3 is never blank).
- **2026-11-02** — **Zero exact duplicate claim lines**: no (member_id, date_svc, diag1)
  group has >1 row in all 1,919,983 rows. A claims row IS a distinct member-day-diagnosis
  fact; no dedup step needed (and the absence of resubmission dupes is a synthetic tell).
- **2026-11-02** — Member id space is the real universe: ids `M0000001..M0291614`,
  **291,611 of 291,614 used** across the two tables (unused: M0059615, M0068175,
  M0200192). Split: 194,290 both / 50,876 claims-only / 46,445 rx-only, uniform across
  the id range. Table membership is strongly negatively correlated (independence predicts
  ~8.1k members in neither, observed 3): the generator gave essentially everyone ≥1 event,
  so there is **no observable zero-utilization population**, and the brief's "200,000
  members" is really ~291.6k.
- **2026-11-02** — Rx follows claims coherently (verified via first-fill-after-claim-day,
  rx members, days ≤2018-05-05): fills follow **R-only (symptom) days almost like
  diagnosis days** (48.1% vs 51.8% within 7d, median gap 2d both) and Z-only checkup days
  much less (37.2%, median 5d). Follow-on drugs make clinical sense: contraceptives are #1
  after Z-only days (gyn exams), ulcer drugs #1 after R-only days (abdominal pain is the
  top R code). Symptom/admin-only members are genuinely light rx users: 50.9% have no
  fills at all vs 82.5% rx presence for condition-diagnosed members (median 3 vs 7 fills).
- **2026-11-02** — No-fill ranking (share of a category's claim-days with NO fill ≤30d;
  baseline 25.5%): drug-free care concentrates exactly where clinic sense says — normal
  pregnancy/delivery 55.5%, pregnancy complications 43.9%, **immunizations/screening 43.8%
  (40.1% of its members never fill after one — behavioral case for re-bucketing it)**,
  sprains 40.0%, fractures 37.8%, benign neoplasms 34.6%, Liveborn 39.4%. Most-filled:
  COPD 11.0%, diabetes w/ compl. 11.3%, ADHD 11.4%, hypertension 13.8%, asthma 14.7%,
  respiratory infections 16.3%. Caveat: measures ANY fill after (not a matching drug), so
  no-fill rates are lower bounds on drug-free management. This is req-2's predictability
  tiering, derived empirically.
- **2026-11-02** — Fills are tightly claim-anchored: for both-table members (fills
  2016-09+, full 365d lookback inside claims coverage) median gap to the last prior claim
  is **11 days**; only 7.7% of fills lack any claim in the prior year (12.0% lack a
  condition claim). Unpreceded skews to maintenance therapy (vaccines 13.5%,
  contraceptives 12.7%, ADHD 12.6%, antipsychotics/antidepressants ~11%) while acute
  categories are visit-glued (cough/cold, urinary anti-infectives, fluoroquinolones,
  antiemetics: ~3% unpreceded, median gap 0 days). Structurally unprecedented: rx-only
  members' 255,852 fills (8.5% of all) — and their mix is NOT healthy-light: antidepressants
  #1, plus antihypertensives, antidiabetics (2,409 members), anticonvulsants, thyroid.
  (Counted 46,446 rx-only here vs 46,445: M0061560's single claim is pre-2015.) Also
  10.4% of all fills predate claims coverage entirely (before 2015-09) — left-censored.
- **2026-11-02** — The "claims run to 2018-12" end was a max-date mirage like the 1899 min:
  only **6 stray claim rows** sit after 2018-06-04, and BOTH feeds taper out together
  (claims Mar 118k → Apr 68k → May 15k, last dense date 2018-05-26; rx Mar 173k → Apr
  141k → May 58k → 632 June fills through 06-04). The only real coverage mismatch is the
  LEFT edge (rx reaches back to 2013-12; 10.4% of fills pre-date claims). Docs corrected
  (CLAUDE.md base tables + mistake 8, data dictionary).
- **2026-11-02** — Canonical window [2015-09-01, 2018-06-04] prices out as: claims lose
  231 rows (0.012%) and 15 members; rx loses 311,585 fills (10.4%) and 10,322 members
  (their fills are all pre-window). In-window populations: **282,734 union = 192,830 both
  / 52,321 claims-only / 37,583 rx-only**; 8,877 of the 291,611 universe have no event
  inside the window at all.
- **2026-11-02** — Mistake 12 bit our own docs: the rx hierarchy counts were the
  profiler's `approx_count_distinct` values. Exact: **92 categories / 464 groups /
  687 classes / 20,368 NDCs** (docs said 90/477/684/21,400). CLAUDE.md + dictionary
  corrected; treat every "distinct (approx)" in the AUTO profile as approximate.
- **2026-11-02** — Rx pass (canonical window; 230,413 members, 2,694,349 fills): fills per
  member median 5 / mean 11.7 / p99 94 / max 669; distinct classes per member median 3.
  Breadth vs depth split: antibiotics touch the most members (Penicillins 20.1%,
  Macrolides 15.1%, ~1.4 fills/member) while chronic classes rack up fills
  (Antidepressants 17.4% of members but 241,706 fills ≈ 6/member). Persistence: 57.1% of
  the 1,005,177 member×class pairs are single-fill; **21.8% are sustained (≥3 fills over
  ≥90d); 36.7% of rx members have ≥1 sustained class** — the natural rx-side chronicity
  flag. Sustained share ladder is textbook chronic→acute: antiretrovirals 55.8%, thyroid
  50.0%, amphetamines(ADHD) 49.5%, insulin 48.4% … toxoids 0.0%, bowel evacuants 0.2%,
  neuraminidase inhibitors 0.2%. Same-class inter-fill gaps: modal ~28-30d (41.9% in the
  25–35d band, median 33d) with clear 60d and ~85-90d harmonics — a real refill cycle;
  odd isolated blip at gap=68d (unexplained, likely generator artifact). Concentration:
  drug_class saturates (top 100 = 87% of fills) while NDC is flat (top 100 = 19%) and raw
  diag codes middling (top 1,000 = 78% of rows) — class is the right rx feature grain,
  NDC unusable, and claims-side grouping (CCS) is similarly justified empirically.
- **2026-11-02** — Pareto check on code frequencies (CCDF log-log + Hill MLE): diagnostic
  codes have a genuine **Pareto tail (α≈2.2 for the ~475 codes with ≥712 rows**, straight
  over two decades, KS 0.024) with a lognormal-ish body (μ=2.1, σ=1.9). Drug classes are
  NOT convincingly Pareto: lognormal (μ=5.1, σ=3.0) tracks them better and the tail is
  truncated (only 669 values, finite window). Both are heavy-tailed either way — the
  practical Pareto-principle concentration holds regardless of the parametric family.
- **2026-11-02** — Repetition structure (member×condition pairs, canonical window, ≥365d
  runway; n=421,072): shape mix = **59.8% single / 23.6% bounded arc (span≤180d) / 11.8%
  recurrent (>180d quiet gap, returns) / 4.9% continuous (span>180d, no long gap)**. The
  current chronic rule (≥2 dates ≥30d apart) decomposes into **44.2% arc + 39.4% recurrent
  + only 16.3% continuous** — 5 of 6 current "chronic" flags are not continuous management.
  Arcs genuinely end (median 636d of silence afterwards). Category signatures are textbook:
  fractures 52.6% arc / 7.8% cont+rec (follow-up cadence ~10d); sprains 27.6% arc / 7% c+r;
  vs diabetes w/compl 19.7% cont + 22.8% rec (check-in gap ~63d), hypertension 10.7+24.3
  (gap ~91d), thyroid 7.9+22.7 (83d). Two visit rhythms: episode follow-ups ~10–21d,
  chronic check-ins ~60–92d. Traps: respiratory infections have long spans via
  REINFECTION (20.1% recurrent, 3.5% continuous — span alone would misread them as
  chronic); mood/anxiety look arc-y in claims (<9% continuous) though clinically chronic —
  their chronicity lives in rx (SSRIs/antidepressants are top sustained classes), so
  claims-shape needs rx corroboration for psych + recurrent-infection categories.
- **2026-11-02** — Joint claims×rx EDA (canonical window). Fills/member separates
  maintenance from acute within the top classes: statins 4.1, SSRIs 4.9, thyroid 5.1,
  ADHD amphetamines 6.1 vs NSAIDs 1.9, glucocorticoids 1.6. Refill buckets (member×class
  pairs: 72.6% 1-2 fills / 13.3% 3-4 / 14.1% 5+): SSRIs 33.5% 5+, statins 29.7%, ACE 29.3%
  vs antibiotics ≈1%, vaccines 0.2%. Caveat: PRN/inhaler classes (nasal steroids, beta
  adrenergics 6.7% 5+) read acute by fill counts though asthma is chronic — one inhaler
  lasts months. Median-split tiers (distinct L2 conditions, med=2; distinct classes,
  med=3) over the 282,734 in-window union: high-dx×high-rx corner = 22.4%; concordant
  low/none mass ≈27%; discordant extremes are symmetric and real — 6,133 members high-rx
  with NO claims and 6,253 high-dx with NO fills (2.2% each). Spearman ρ(conditions,
  classes)=0.543 among both-table members. Condition×class LIFT heatmap confirms wiring:
  metformin×diabetes 8×, antidepressants×mood 7×, urinary anti-infectives×urinary 7×,
  ophthalmic antibiotics×eye 6×, thiazides×hypertension 5×, opioids/muscle-relaxants×
  fractures/back ~5× (injuries DO have an rx tie, but non-specific analgesia);
  screening/respiratory rows run slightly BELOW 1× against cardiometabolic classes.
