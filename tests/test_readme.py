"""README.md's AUTO sections must match the files they describe (`make readme` fixes)."""

import subprocess
import sys

from oscar_cs.paths import ROOT


def test_readme_auto_sections_in_sync():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_readme.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
