"""Enforce a branch-coverage floor, read from pyproject.toml at run time.

coverage.py's ``fail_under`` gates the combined line+branch total. This script
gates branch coverage specifically, so a module with high line coverage but
untested conditional branches still fails the gate (AC-CH-3).

Usage::

    coverage run ... && coverage json -o coverage.json
    python tools/check_branch_coverage.py [coverage.json]

The floor is read from ``[tool.coverage.report].branch_fail_under`` in
pyproject.toml — never hard-coded here or in the Makefile (rule G003 / C-CH-2).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _read_branch_floor(pyproject: Path) -> int | None:
    """Read branch_fail_under from pyproject without a TOML dependency.

    Works on Python 3.10 (no tomllib). The key lives under
    ``[tool.coverage.report]``; the first match wins.
    """
    if not pyproject.exists():
        return None
    in_section = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == "[tool.coverage.report]"
            continue
        if not in_section:
            continue
        match = re.match(r"branch_fail_under\s*=\s*(\d+)", stripped)
        if match:
            return int(match.group(1))
    return None


def branch_coverage(cov_path: Path) -> tuple[float, int, int]:
    data = json.loads(cov_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    num = int(totals.get("num_branches", 0))
    covered = int(totals.get("covered_branches", 0))
    pct = (100.0 * covered / num) if num else 0.0
    return pct, covered, num


def main(argv: list[str]) -> int:
    cov_path = Path(argv[1]) if len(argv) > 1 else Path("coverage.json")
    pyproject = Path("pyproject.toml")
    floor = _read_branch_floor(pyproject)

    if floor is None:
        print("no branch_fail_under set in pyproject.toml; skipping branch gate")
        return 0

    if not cov_path.exists():
        print(f"coverage file not found: {cov_path}; run coverage first", file=sys.stderr)
        return 2

    pct, covered, num = branch_coverage(cov_path)
    if num == 0:
        print("no branches measured; skipping branch gate")
        return 0

    if pct < floor:
        print(
            f"branch coverage {pct:.1f}% ({covered}/{num} branches) "
            f"below floor {floor}% from pyproject.toml"
        )
        return 1
    print(f"branch coverage {pct:.1f}% ({covered}/{num}) meets floor {floor}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
