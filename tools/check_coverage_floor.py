"""Enforce the line-coverage floor, read from pyproject.toml at run time.

coverage.py's ``--cov-fail-under`` CLI flag takes a number, which would hard-code
the threshold into the Makefile — exactly the anti-pattern rule G003 / C-CH-2
forbids. This script reads ``fail_under`` from
``[tool.coverage.report]`` in pyproject.toml and gates line coverage against it,
so the threshold lives in one place (the config), never in CI config.

Usage::

    coverage run ... && coverage json -o coverage.json
    python tools/check_coverage_floor.py [coverage.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_pyproject_int


def _read_floor(pyproject: Path) -> int | None:
    """Read fail_under from [tool.coverage.report], anchored at the repo root."""
    return read_pyproject_int(pyproject, "[tool.coverage.report]", "fail_under")


def line_coverage(cov_path: Path) -> tuple[float, int, int]:
    data = json.loads(cov_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    num = int(totals.get("num_statements", 0))
    covered = int(totals.get("covered_lines", 0))
    pct = (100.0 * covered / num) if num else 0.0
    return pct, covered, num


def main(argv: list[str]) -> int:
    cov_path = Path(argv[1]) if len(argv) > 1 else Path("coverage.json")
    floor = _read_floor(Path("pyproject.toml"))

    if floor is None:
        # A repo that turns this gate on MUST configure fail_under. Missing it is
        # a misconfiguration, not a skip — fail loud so CI never passes silently.
        print("no fail_under set in pyproject.toml [tool.coverage.report]", file=sys.stderr)
        return 2

    if not cov_path.exists():
        print(f"coverage file not found: {cov_path}; run coverage first", file=sys.stderr)
        return 2

    pct, covered, num = line_coverage(cov_path)
    if num == 0:
        print("no statements measured; is coverage configured for the source?", file=sys.stderr)
        return 2

    if pct < floor:
        print(f"line coverage {pct:.1f}% ({covered}/{num}) below floor {floor}% from pyproject.toml")
        return 1
    print(f"line coverage {pct:.1f}% ({covered}/{num}) meets floor {floor}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
