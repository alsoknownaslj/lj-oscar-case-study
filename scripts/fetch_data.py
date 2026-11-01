"""Download the case-study files from Google Drive into data/raw/.

Requires the Drive folder (or each file) to be shared "anyone with link can view":
https://drive.google.com/drive/u/0/folders/1h4W_vrdIimrIQsGILMqhxTaatpzukWzU

Downloads hit https://drive.usercontent.google.com/download directly via curl
(with gdown as a fallback). gdown alone is NOT used first on purpose: it bounces
through doc-XX-XX-docs.googleusercontent.com mirror hosts, which restricted
networks (e.g. Claude cloud environments) don't allowlist; the direct endpoint
needs only drive.google.com + drive.usercontent.google.com.

Usage: python scripts/fetch_data.py [--force]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REFS = ROOT / "references"

# (drive file id, expected bytes, destination)
FILES = {
    "claim_lines.csv": ("19VdJ5WDuoPXECBzJTY3DXClOvJpVaOMt", 65_345_631, RAW),
    "prescription_drugs.csv": ("1IQNse3HswUzLlvrGO7lMckyeTHML2RD8", 371_337_198, RAW),
    "ccs.csv": ("1tzvnG-PRr4Q3YqCy9wcuT5VuLehrx7G2", 10_904_504, RAW),
    "Oscar_Data_Science_Case_Study.pdf": ("18LiL2iN5K5DydBeBY4QIQ9d0yMlOqSwY", 60_610, REFS),
}

HELP = """
Download failed. Three ways to unblock:
  1. Sharing: set the Drive folder to "anyone with link can view" and rerun.
  2. Running in a Claude cloud session? The environment must allow the domains
     drive.google.com and drive.usercontent.google.com (environment menu -> Edit
     -> Network access -> Allowed domains).
  3. Manual: download the files from the Drive folder in your browser straight
     into data/raw/ (the PDF into references/) - then rerun this script to verify.
"""


def download(file_id: str, dest: Path) -> None:
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    if shutil.which("curl"):
        res = subprocess.run(
            ["curl", "-sL", "--fail", "--retry", "3", "--retry-delay", "2", "-o", str(dest), url],
            check=False,
        )
        if res.returncode == 0:
            return
        print(f"       curl exited {res.returncode}; trying gdown fallback")
    try:
        import gdown

        gdown.download(id=file_id, output=str(dest), quiet=True)
    except ImportError:
        print("       gdown not installed (pip install gdown) and curl failed")
    except Exception as exc:
        print(f"       gdown error: {exc}")


def main() -> int:
    force = "--force" in sys.argv
    failures = 0
    for name, (file_id, expected, dest_dir) in FILES.items():
        dest = dest_dir / name
        if dest.exists() and dest.stat().st_size == expected and not force:
            print(f"[ok]   {name} already present ({expected:,} bytes)")
            continue
        print(f"[get]  {name} ({expected / 1e6:.1f} MB) ...")
        download(file_id, dest)
        got = dest.stat().st_size if dest.exists() else 0
        if got != expected:
            print(f"[FAIL] {name}: got {got:,} of {expected:,} bytes")
            if dest.exists():
                dest.unlink()  # don't leave a partial/HTML file masquerading as raw data
            failures += 1
        else:
            print(f"[ok]   {name} downloaded ({expected:,} bytes)")

    if failures:
        print(HELP)
        return 1

    print("\nAll files present. Next: make cache && make profile")
    print("Then follow the first-run checklist in CLAUDE.md -> 'Data status'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
