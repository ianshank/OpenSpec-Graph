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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_pyproject_int


def _read_branch_floor(pyproject: Path) -> int | None:
    """Read branch_fail_under from [tool.specgraph], anchored at the repo root.

    This is specgraph's own gate key, kept out of ``[tool.coverage.*]`` so
    coverage.py doesn't warn about an unknown option.
    """
    return read_pyproject_int(pyproject, "[tool.specgraph]", "branch_fail_under")


def branch_coverage(cov_path: Path) -> tuple[float, int, int]:
    data = json.loads(cov_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    num = int(totals.get("num_branches", 0))
    covered = int(totals.get("covered_branches", 0))
    pct = (100.0 * covered / num) if num else 0.0
    return pct, covered, num


def main(argv: list[str]) -> int:
    cov_path = Path(argv[1]) if len(argv) > 1 else Path("coverage.json")
    floor = _read_branch_floor(Path("pyproject.toml"))

    if floor is None:
        # A repo that turns this gate on MUST configure branch_fail_under.
        # Missing it is a misconfiguration, not a skip — fail loud so CI never
        # passes silently on a gate it claims to enforce.
        print("no branch_fail_under set in pyproject.toml [tool.specgraph]", file=sys.stderr)
        return 2

    if not cov_path.exists():
        print(f"coverage file not found: {cov_path}; run coverage first", file=sys.stderr)
        return 2

    pct, covered, num = branch_coverage(cov_path)
    if num == 0:
        # branch=true is set in pyproject; zero branches means coverage didn't
        # instrument the source at all — a real misconfiguration, not a pass.
        print(
            "no branches measured; is branch=true set and source instrumented?",
            file=sys.stderr,
        )
        return 2

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
