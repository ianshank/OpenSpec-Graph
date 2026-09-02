"""Fail if a numeric threshold, tool version, or pinned path is hard-coded in
the Makefile or any CI workflow YAML (AC-EH-6, rule G003 / C-CH-2).

Thresholds must live in ``pyproject.toml`` and be read by scripts at run time.
This guard catches a regression where someone re-introduces a bare number into
the Makefile (e.g. ``--cov-fail-under=90``) or pins a tool version in the
workflow instead of the dev extras.

Allowed: comments, the Makefile's own ``$(MAKE)`` recursion, and the literal
``0``/``1`` exit codes. Flagged: any other integer appearing on a command line
in the Makefile, or a ``fail-under``/``fail_under``/``--cov-fail-under`` literal
in any workflow.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import repo_root

REPO_ROOT = repo_root()

# Lines in the Makefile / workflows that legitimately carry numbers. We match on
# intent, not a blanket "any digit" rule, so legitimate targets stay green.
_ALLOWED_PATTERNS = (
    re.compile(r"^\s*#"),           # comments
    re.compile(r"\$\("),           # make variables / functions
    re.compile(r"@\w"),            # @echo / @grep recipe prefixes
    re.compile(r"\bmake\b", re.IGNORECASE), # invoking make recursively
)

# A numeric literal on a recipe/CI command line that is NOT an exit code 0/1.
_THRESHOLD_TOKEN = re.compile(r"(?<![\w.-])(\d{2,})(?![\w.])")


def _is_allowed(line: str) -> bool:
    return any(pattern.search(line) for pattern in _ALLOWED_PATTERNS)


def check_makefile(path: Path) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return findings
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(".PHONY"):
            continue
        if _is_allowed(line):
            continue
        for match in _THRESHOLD_TOKEN.finditer(line):
            value = match.group(1)
            findings.append(f"{path}:{lineno}: hard-coded numeric literal '{value}' in: {stripped}")
    return findings


def check_workflow(path: Path) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return findings
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        # A coverage floor pinned in the workflow instead of pyproject.
        if re.search(r"(--cov-fail-under|fail[-_]under)\s*[:=]\s*\d", line):
            findings.append(f"{path}:{lineno}: coverage floor pinned in workflow, not pyproject: {line.strip()}")
        # A python-version pin is allowed (matrix), but a tool version pin is not.
        if re.search(r"ruff==\d|mypy==\d|pytest==\d", line):
            findings.append(f"{path}:{lineno}: tool version pinned in workflow, use dev extras: {line.strip()}")
    return findings


def main(argv: list[str]) -> int:
    # Every workflow, not just ci.yml. Naming one file meant any workflow
    # added later (a release job, a scheduled scan) escaped this guard
    # silently -- the guard would still print PASS while the new file pinned
    # a coverage floor or a tool version (R-SD-10). Sorted for a stable
    # report order across filesystems.
    workflows = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((REPO_ROOT / ".github" / "workflows").glob("*.yaml"))
    targets = [REPO_ROOT / "Makefile", *workflows]
    findings: list[str] = []
    for target in targets:
        findings.extend(check_makefile(target) if target.name == "Makefile" else check_workflow(target))

    if findings:
        for message in findings:
            print(f"FAIL: {message}")
        return 1
    print("PASS: no hard-coded thresholds in Makefile or workflow YAML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
