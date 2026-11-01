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
