---
name: healthcare-claims
description: >-
  Healthcare-data judgment for this repo's claims, diagnosis and prescription tables. Use
  whenever interpreting ICD-10 codes, CCS categories, NDC drug codes, claim lines, fills,
  or member-level health constructs — before designing features, labels, cohorts, or
  condition flags. Triggers: ICD, diagnosis, CCS, NDC, drug class, claims, member health,
  condition, chronic, utilization.
---

# Healthcare claims & rx data — judgment for this case study

Mechanical facts about the code systems live in `references/domain-notes.md` (read it
first). This skill is how to *reason* with them. Hard rules are **(rule)**.

## Reading claims correctly

- A diagnosis code on a claim line means "a clinician coded this on that date" — not
  "the member has this disease". Single occurrences include rule-outs, screenings, and
  misc visit coding. **(rule)** Chronic-condition flags need corroboration: the standard
  heuristic is ≥2 claim-line dates with the condition ≥30 days apart (1 suffices for
  acute events like fractures — say which rule each condition uses).
- Z-codes (factors influencing health status) and the CCS "Symptoms; signs; and
  ill-defined" + "Residual" chapters are mostly administrative noise for member
  profiling. **(rule)** Decide and document their treatment before aggregating; don't let
  them dominate "top conditions" tables.
- Claim-line volume ≠ severity. Volume mixes utilization behavior, coding habits, and
  care access — the case study itself says unusual patterns (over- AND under-utilization)
  are the interesting signal.
- **(rule)** Denominators: report member-level shares by default ("% of members with ≥1
  X"), never raw row shares, and name the denominator population (all 200k? members with
  any claims? members in both tables?).

## Building the health-status characterization (requirement 1)

- Characterize at a stated CCS level (level 2 is the usual sweet spot; level 1's 18
  chapters usually too coarse). Parse level-2 ids with `parse_ccs2_code`, don't
  string-match descriptions.
- A good characterization is: per member, a small set of condition flags (chronic rules
  above) + light utilization descriptors (claim days, distinct categories, recency). It
  should round-trip to a sentence: "member xyz: diabetes + hypertension; 14 claim days
  across 2.5 years." Produce 2–3 such vignettes as a sanity check before any modeling.
- Track the unmapped: codes with no CCS row and members whose entire history is
  unmapped/residual. Quantify, then decide (exclude vs "unclassified" bucket) — never
  silent inner-join loss. **(rule)**

## Reading prescription data

- One row = one fill, not one prescription decision — refills repeat. Persistence
  (same class across months) separates chronic therapy from one-offs.
- Model/aggregate on the provided category → group → class hierarchy, not raw NDC.
  **(rule)** NDC stays a string everywhere (leading zeros).
- Drug→condition inference has tiers — treat them differently and say so:
  strong (insulin/antidiabetics → diabetes; antiretrovirals → HIV; antineoplastics →
  cancer), moderate (statins, antihypertensives, inhalers, antidepressants — common,
  mostly condition-specific), weak (antibiotics, analgesics, PPIs — acute/symptomatic,
  near-zero chronic signal). Expect and report that model performance follows these tiers.

## Hygiene

- Data is simulated (no real PHI) — keep real-PHI habits anyway: no member-level rows or
  quasi-identifying vignette details in committed reports beyond invented ids; aggregates
  ≥ small-cell threshold (suppress n<11 cells if publishing anything). **(rule)**
- Dates: 3-year window with unknown enrollment spans. A member with no claims in year 3
  may be healthy — or disenrolled. Name this censoring limitation in every write-up.
- When unsure whether a pattern is data-generation artifact vs. realistic signal
  (it IS synthetic), check `memory/data-quirks.md` first, add to it after.
