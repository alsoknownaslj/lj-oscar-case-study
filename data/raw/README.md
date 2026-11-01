# data/raw — immutable inputs

The three case-study CSVs belong here, exactly as downloaded (never edited, re-sorted, or
overwritten). Get them with `python scripts/fetch_data.py` (needs the Drive folder set to
"anyone with link") or download manually from the
[Drive folder](https://drive.google.com/drive/u/0/folders/1h4W_vrdIimrIQsGILMqhxTaatpzukWzU):

| file | size | in git? |
|---|---|---|
| `claim_lines.csv` | 65 MB | no (gitignored — GitHub 100 MB limit) |
| `prescription_drugs.csv` | 371 MB | no (gitignored) |
| `ccs.csv` | 11 MB | yes, once fetched |

`_partial/` holds the 1 MB head of `ccs.csv` recovered via the Drive connector on
2026-10-31 (local-only); the committed 400-row sample is `references/samples/ccs_sample.csv`.

After files land: `make cache && make profile`, then follow the first-run checklist in
`CLAUDE.md` → "Data status".
