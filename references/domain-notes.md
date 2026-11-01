# Domain notes — healthcare coding systems in this project

Working primer for the three vocabularies in play. Deeper judgment calls live in the
`healthcare-claims` skill (`.claude/skills/healthcare-claims/`).

## ICD-10-CM (diagnosis codes, `claim_lines` + `ccs.diag`)

- Structure: 3–7 alphanumeric chars. First char is a letter (chapter), chars 1–3 are the
  category, chars 4–7 add etiology/site/severity. Written form puts a dot after the 3rd
  char (`A00.0`); stored forms often drop it (`A000` — as `ccs.diag` does).
- Normalization for joins: uppercase, strip whitespace and dots. Never truncate to 3 chars
  to force a match — that changes clinical meaning; measure unmatched codes instead.
- A diagnosis on a claim means a clinician *coded* it that day — includes rule-outs,
  screenings (Z-codes), and administrative visits. Repetition across dates is a better
  chronic-condition signal than a single occurrence.

## CCS — Clinical Classifications Software (AHRQ/HCUP)

- Purpose: collapse ~70k ICD-10-CM codes into analyzable clinical categories.
  Reference: <https://www.hcup-us.ahrq.gov/toolssoftware/ccs10/ccs10.jsp>
- **Multi-level**: level 1 = 18 broad chapters; level 2 ≈ 130s of categories (our
  `ccs_2_desc` embeds numeric ids like `[135.]`); level 3 = finest, often equal to level 2.
- Level choice drives everything downstream: L1 is usually too coarse to say more than
  "has a circulatory problem"; L2 is the common sweet spot for member profiling.
- Known traps: the residual/unclassified chapter; "Symptoms; signs; and ill-defined
  conditions" (lots of volume, little specificity); not all ICD-10 codes map at all.

## NDC — National Drug Code (`prescription_drugs`)

- 10- or 11-digit, 3 segments: labeler–product–package (e.g. `0002-1433-80`). Padding to
  11 digits (5-4-2) is the standard normalization. **Leading zeros are meaningful** — NDC
  columns are strings, always.
- NDC identifies a *package* of a drug product, not a molecule: one drug ⇒ many NDCs.
  For inference, the provided `drug category / group / class` hierarchy is the usable
  feature space — don't model on raw NDC (hundreds of thousands of sparse levels).

## Inferring conditions from drugs (requirement 2 intuition)

Drug classes are strong proxies for chronic conditions: antidiabetics → diabetes;
statins/antihypertensives → cardiovascular risk; inhaled bronchodilators/corticosteroids →
asthma/COPD; antidepressants/antipsychotics → mental illness; antineoplastics → cancer;
antiretrovirals → HIV. Weak/ambiguous: antibiotics, analgesics, PPIs (acute, broad, or
symptomatic use). Expect the model to do well on chronic, drug-managed conditions and
poorly on injuries, screenings, and conditions managed procedurally — that asymmetry is a
finding worth reporting, not a failure.

Fill-rate patterns add signal beyond class membership: persistence (refills over months)
separates chronic therapy from one-off scripts.

## Vocabulary quick reference

| term | meaning here |
|---|---|
| member | one insured person (`member_id`-level is the unit of analysis) |
| claim line | one diagnosis × member × date row in `claim_lines` |
| utilization | the volume/pattern of claims or fills, not their cost |
| member-month | denominator unit when exposure windows differ (3-year window here) |
| fill | one dispensed prescription row in `prescription_drugs` |
