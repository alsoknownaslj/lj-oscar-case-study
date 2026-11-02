# Data quirks — durable facts about the dataset

Append as discovered (newest last). Every entry: fact + how it was verified.
(2026-11-02: analysis-finding entries compacted into the digest at the bottom; full
detail lives in `reports/2026-11-02_eda-session.md`.)

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
  prescription_drugs 371,337,198; ccs 10,904,504.
- **2026-10-31 (full data verified)** — Real schemas: claims = `record_id, member_id,
  date_svc, diag1` (1,919,983 rows, record_id unique); rx = `record_id, member_id,
  date_svc, ndc, drug_category, drug_group, drug_class` (3,005,934 rows; record_id =
  19-digit ints — string, never float). `diag1` 91.9% dotted; normalized join → 99.89% CCS
  row coverage, 217 distinct codes unmapped.
- **2026-10-31** — Dirty-by-design values in claims: 24 null `date_svc` + 38 rows dated
  1899–2014 (sentinels/strays); 63 rows of diag `000`; one `"L02.,821"` comma code at row
  1,783,434 — which also means **the CSV has quoted fields: always parse with
  `quote='"'`** (duckdb's sniffer sees no quotes in the first 20k rows and errors).
- **2026-10-31** — Raw-table members: 245,166 claims / 240,735 rx / **194,290 in both**;
  the brief's "200,000 members" is nominal.
- **2026-10-31** — `ccs_3_desc` never blank; `diag` unique. NDC: all 11-digit, leading
  zeros intact.
- **2026-11-01** — Claims window correction: volume ramps from **2015-09**, not 2015-12
  (Jan–Aug 2015 ≈163 rows; peak 2016). Verified via duckdb monthly counts.
- **2026-11-01** — Exact cleaning numbers (pre-canonical-window rule): 24 null dates +
  **38** pre-2015 rows; exactly one member (M0061560, single 2014-08-08 claim) drops —
  they have 11 rx fills, so the raw both-tables overlap reads 194,289 after cleaning.
- **2026-11-01** — Top unmapped codes: `99999` (biggest, previously undocumented), `KHDX`,
  `000`. 217 distinct unmapped confirmed exactly.
- **2026-11-01** — Profiling trap confirmed: the Symptoms/Z-code chapter is 18.1% of kept
  claim rows; "Factors influencing health care" alone touches **53.9% of members** —
  left in, it would be the #1 "condition". Residual chapter: 1.6% of rows.
- **2026-11-02** — Correction: Residual-chapter `ccs_2_desc` is a **single space `' '`**,
  not an empty string — `nullif(x, '')` and `== ''` miss it; strip/trim first. No level-2
  name spans two chapters; Residual has no level 2 but **22 level-3 categories**.
- **2026-11-02** — **Zero exact duplicate claim lines** in all 1,919,983 rows: a claims
  row IS a distinct member-day-diagnosis fact; no dedup needed (synthetic tell).
- **2026-11-02** — Member id space is the real universe: `M0000001..M0291614`,
  **291,611 of 291,614 used** (unused: M0059615, M0068175, M0200192). Split: 194,290
  both / 50,876 claims-only / 46,445 rx-only, uniform across the range. Independence
  predicts ~8.1k members in neither table; observed 3 — **no observable zero-utilization
  population**; the universe is ~291.6k.
- **2026-11-02** — The "claims run to 2018-12" end was a max-date mirage like the 1899
  min: only **6 stray claim rows** sit after 2018-06-04, and BOTH feeds taper out
  together over Apr–May 2018 (claims last dense date 2018-05-26; rx 632 June fills to
  06-04). The only real coverage mismatch is the LEFT edge (rx reaches back to 2013-12;
  10.4% of fills pre-date claims coverage).
- **2026-11-02** — Canonical window [2015-09-01, 2018-06-04] prices out as: claims lose
  231 rows (0.012%) / 15 members; rx loses 311,585 fills (10.4%) / 10,322 members.
  In-window populations: **282,734 union = 192,830 both / 52,321 claims-only / 37,583
  rx-only**; 8,877 of the universe have no in-window event.
- **2026-11-02** — Mistake 12 bit our own docs: rx hierarchy counts were the profiler's
  `approx_count_distinct`. Exact: **92 categories / 464 groups / 687 classes / 20,368
  NDCs**. Treat every "distinct (approx)" in the AUTO profile as approximate.
- **2026-11-02 — EDA findings digest** (full detail + figures:
  `reports/2026-11-02_eda-session.md`; scripts: `scripts/eda/`):
  - Rx is claim-anchored: median fill sits 11d after the last claim; 7.7% of fills lack a
    prior-year claim (skew: maintenance therapy); R-symptom days are followed by fills
    almost like diagnosis days (48.1% vs 51.8% ≤7d, median 2d), Z-checkup days much less.
  - Least-filled diagnoses: pregnancy, **immunizations/screening**, injuries, benign
    neoplasms; most-filled: COPD, diabetes, ADHD, hypertension, asthma — req-2's
    feasibility map. Rx-only members are NOT healthy-light (antidepressants #1,
    antidiabetics 2,409 members).
  - Refill mechanics: 41.9% of same-class gaps in the 25–35d band (median 33d; 60/90d
    harmonics; odd 68d blip = likely artifact). 21.8% of member×class pairs sustained
    (≥3 fills ≥90d); 36.7% of rx members have ≥1 sustained class. PRN/inhaler classes
    read acute by fill counts though the condition is chronic.
  - Code concentration: top 180 diag codes = 50% of rows; top 24 classes = 50% of fills;
    NDC unusable (top 10 = 4%). Diag codes have a real Pareto tail (α≈2.2, x≥712, KS
    0.024) over a lognormal body; classes read lognormal, truncated.
  - Repetition shapes (≥365d-runway pairs): 59.8% single / 23.6% arc / 11.8% recurrent /
    4.9% continuous. The draft chronic rule decomposes 44.2% arc + 39.4% recurrent +
    16.3% continuous. Fractures = arcs (~10d cadence); diabetes/HTN/thyroid = 60–92d
    check-ins; respiratory fakes chronicity by reinfection; psych chronicity lives in rx.
  - Joint: all four claims×rx metric pairings correlate ρ 0.49–0.54; joint deciles run
    2.0× (light-light) and 4.5× (heavy-heavy) over independence, 0.11× discordant;
    ~8.3k heavy-rx members have zero claims and ~8.1k heavy-dx members zero fills. Lift
    wiring: metformin×diabetes 8×, antidepressants×mood 7×, thiazides×HTN 5×.
  - Volumes: dx lines p50 4 / p90 18 / p99 63 / max 914; fills p50 5 / p90 29 / p99 94 /
    max 669. Raw IQR flags ~10% (useless); **518 members above p99 on both axes vs ~19
    expected (27×)** — the extreme tail is a joint sub-population. Median member×class
    AND member×condition pair is a single touch; dx line-depth does NOT separate chronic
    from episodic (visit-dense back/joint episodes top it) while rx depth does.
- **2026-11-02 (final build)** — In-window unmapped distinct codes = **216** (vs 217
  all-time: one junk code lives only in the excluded 1899–2014 stray rows). v2 bucket
  rows (canonical window): condition 1,509,935 / admin-Z 250,060 / symptoms-R 96,978 /
  immunizations 29,164 / residual 31,625 / unmapped 1,990. All EDA cross-checks
  (union 282,734 split, p99 63/94, 518 joint-p99 vs 19.6) reproduced exactly in the
  rebuilt pipeline.
- **2026-11-02** — The most multimorbid claims member (34 chronic conditions, 914 claim
  lines = the max) has **zero in-window fills**: a high-dx / no-rx discordant member,
  not part of the joint >p99 segment. An earlier draft captioned them as that segment
  without checking. Verified in member_health_status.parquet (rx_fills 0,
  dx_above_p99 True, rx_above_p99 False). Rule: verify a vignette's flags before
  attaching any segment claim to it.
