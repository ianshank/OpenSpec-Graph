"""Confirm the enterprise documentation set exists and is linked from README
(AC-EH-8). A missing or unlinked doc fails the gate — docs that aren't
discoverable from README are effectively absent for a new contributor.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = [
    "CHANGELOG.md",
    "docs/architecture/c4.md",
    "docs/aqa.md",
    "docs/hooks.md",
    "docs/agents-skills-harness.md",
    "docs/next-steps.md",
]


def check(root: Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    readme = (root / "README.md")
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    for doc in REQUIRED_DOCS:
        if not (root / doc).exists():
            problems.append(f"MISSING: {doc}")
        elif doc not in readme_text:
            problems.append(f"UNLINKED: {doc} not referenced in README.md")
    return problems


def main(argv: list[str]) -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("docs-check: all required docs present and linked from README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
