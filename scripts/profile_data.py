"""Profile the raw tables and rewrite the AUTO section of references/data-dictionary.md.

duckdb-only (no pandas) so the 371 MB prescription file profiles in-place without memory
drama. Generic per-table profile plus case-study-specific cross-checks:
  - dot formatting of ICD-10 codes in claim_lines vs ccs
  - CCS join coverage (rows and distinct codes)
  - member overlap between claims and prescriptions

Usage: python scripts/profile_data.py
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DICT = ROOT / "references" / "data-dictionary.md"
AUTO_BEGIN, AUTO_END = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"
TOPK_MAX_DISTINCT = 25  # show value counts for columns at or below this cardinality


def q(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def profile_table(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> str:
    rel = f"read_csv({str(path)!r}, header = true, sample_size = -1, quote = '\"', escape = '\"')"
    (n_rows,) = q(con, f"select count(*) from {rel}")[0]
    cols = q(con, f"describe select * from {rel} limit 0")
    lines = [
        f"### `{path.name}` — {n_rows:,} rows, {path.stat().st_size / 1e6:.1f} MB",
        "",
        "| column | inferred type | null % | distinct (approx) | min | max |",
        "|---|---|---|---|---|---|",
    ]
    details: list[str] = []
    for col, ctype, *_ in cols:
        nulls, nd, cmin, cmax = q(
            con,
            f"""
            select
                round(100.0 * sum(case when "{col}" is null then 1 else 0 end) / count(*), 2),
                approx_count_distinct("{col}"),
                min("{col}")::varchar, max("{col}")::varchar
            from {rel}
            """,
        )[0]
        lines.append(f"| `{col}` | {ctype} | {nulls} | {nd:,} | {cmin} | {cmax} |")
        if ctype.upper().startswith(("BIGINT", "INTEGER", "DOUBLE")) and re.search(
            r"(code|ndc|diag|icd)", col, re.I
        ):
            details.append(
                f"- ⚠️ `{col}` auto-typed as {ctype} but looks like a code column — "
                "leading zeros may be lost here; the parquet cache keeps it VARCHAR."
            )
        if nd and nd <= TOPK_MAX_DISTINCT:
            top = q(
                con,
                f'select "{col}"::varchar, count(*) from {rel} '
                f"group by 1 order by 2 desc limit {TOPK_MAX_DISTINCT}",
            )
            tv = "; ".join(f"`{v}` ({c:,})" for v, c in top)
            details.append(f"- `{col}` values: {tv}")
    return "\n".join(lines + [""] + details)


def cross_checks(con: duckdb.DuckDBPyConnection, tables: dict[str, Path]) -> str:
    out: list[str] = ["### Cross-table checks", ""]

    def rel(name: str) -> str:
        return (
            f"read_csv({str(tables[name])!r}, header = true, all_varchar = true, "
            f"sample_size = -1, quote = '\"', escape = '\"')"
        )

    def find_col(name: str, pattern: str) -> str | None:
        cols = [c for c, *_ in q(con, f"describe select * from {rel(name)} limit 0")]
        hits = [c for c in cols if re.search(pattern, c, re.I)]
        return hits[0] if hits else None

    try:
        if "claim_lines" in tables and "ccs" in tables:
            dx = find_col("claim_lines", r"diag|icd|dx")
            if dx:
                (dot_claims,) = q(
                    con,
                    f"select round(100.0 * sum(case when \"{dx}\" like '%.%' then 1 else 0 end)"
                    f" / count(*), 1) from {rel('claim_lines')}",
                )[0]
                out.append(
                    f"- `claim_lines.{dx}` rows containing a dot: **{dot_claims}%** "
                    "(ccs.diag is undotted — normalize before joining)."
                )
                cov_rows, cov_codes = q(
                    con,
                    f"""
                    with cl as (
                        select upper(replace(trim("{dx}"), '.', '')) as k from {rel("claim_lines")}
                    ),
                    m as (select upper(trim(diag)) as k from {rel("ccs")})
                    select
                        round(100.0 * sum(case when k in (select k from m) then 1 else 0 end)
                            / count(*), 2),
                        (select count(distinct cl2.k) from cl cl2 where cl2.k in (select k from m))
                    from cl
                    """,
                )[0]
                norm_dx = f"upper(replace(trim(\"{dx}\"), '.', ''))"
                (n_codes,) = q(
                    con,
                    f"select count(distinct {norm_dx}) from {rel('claim_lines')}",
                )[0]
                out.append(
                    f"- CCS join coverage after normalization: **{cov_rows}% of claim rows**; "
                    f"{cov_codes:,} of {n_codes:,} distinct claim codes map."
                )
        mem_cl = find_col("claim_lines", r"member") if "claim_lines" in tables else None
        mem_rx = (
            find_col("prescription_drugs", r"member") if "prescription_drugs" in tables else None
        )
        if mem_cl and mem_rx:
            a, b, both = q(
                con,
                f"""
                with c as (select distinct "{mem_cl}" as m from {rel("claim_lines")}),
                     r as (select distinct "{mem_rx}" as m from {rel("prescription_drugs")})
                select (select count(*) from c), (select count(*) from r),
                       (select count(*) from c join r using (m))
                """,
            )[0]
            out.append(
                f"- Members: {a:,} in claims, {b:,} in prescriptions, **{both:,} in both** "
                "(the rx-only model's labeled population)."
            )
    except Exception as exc:  # keep the generic profile even if a targeted check breaks
        out.append(f"- ⚠️ cross-checks incomplete: {exc}")
    return "\n".join(out)


def main() -> int:
    csvs = {p.stem: p for p in sorted(RAW.glob("*.csv"))}
    if not csvs:
        print("No CSVs in data/raw/ - run `make fetch` first (see CLAUDE.md 'Data status').")
        return 1
    con = duckdb.connect()
    stamp = dt.date.today().isoformat()
    parts = [
        f"_Generated by `scripts/profile_data.py` on {stamp}. Do not edit inside the markers._",
        "",
    ]
    for name, path in csvs.items():
        print(f"profiling {name} ...")
        parts.append(profile_table(con, name, path))
        parts.append("")
    parts.append(cross_checks(con, csvs))
    body = "\n".join(parts)

    text = DICT.read_text()
    # Markers must sit on their own lines: prose may mention them in backticks.
    marker_re = re.compile(rf"^{re.escape(AUTO_BEGIN)}$.*?^{re.escape(AUTO_END)}$", re.S | re.M)
    if not marker_re.search(text):
        raise SystemExit(f"AUTO markers not found on their own lines in {DICT}")
    DICT.write_text(marker_re.sub(lambda _: f"{AUTO_BEGIN}\n{body}\n{AUTO_END}", text, count=1))
    print(f"\nWrote profile into {DICT.relative_to(ROOT)} (between AUTO markers).")
    print("Now reconcile the hand-written schema tables in CLAUDE.md with reality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
