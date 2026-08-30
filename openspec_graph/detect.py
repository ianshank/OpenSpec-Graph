"""Detect a target repository's stack, gates, thresholds, and OpenSpec dialect.

Nothing here writes. Detection is read-only by contract so that `graft detect`
is always safe to run against an unfamiliar clone.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

MANIFESTS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
    "node": ("package.json",),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "jvm": ("pom.xml", "build.gradle", "build.gradle.kts"),
}

# Where invariant/contract IDs are conventionally declared, most specific first.
INVARIANT_SOURCES: tuple[str, ...] = (
    "harness/CONTRACT.md",
    "CONTRACT.md",
    "HARNESS_SPEC.md",
    "docs/CONTRACT.md",
    "docs/HARNESS_SPEC.md",
    "AGENTS.md",
)

_MAKE_TARGET = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:(?!=)", re.MULTILINE)
_INV_ID = re.compile(r"\bINV-\d+\b")
_FAIL_UNDER = re.compile(r"^\s*fail_under\s*=\s*(\d+)", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class ThresholdSource:
    """Where a coverage floor actually lives in this repo."""

    locator: str
    value: int | None

    def as_dict(self) -> dict[str, object]:
        return {"locator": self.locator, "value": self.value}


@dataclasses.dataclass(frozen=True)
class StackProfile:
    root: Path
    languages: tuple[str, ...]
    make_targets: tuple[str, ...]
    openspec_root: Path | None
    change_dirs: tuple[Path, ...]
    dialect: str
    threshold: ThresholdSource | None
    invariant_source: Path | None
    invariant_ids: tuple[str, ...]
    has_project_md: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "languages": list(self.languages),
            "make_targets": list(self.make_targets),
            "openspec_root": str(self.openspec_root) if self.openspec_root else None,
            "change_dirs": [d.name for d in self.change_dirs],
            "dialect": self.dialect,
            "threshold": self.threshold.as_dict() if self.threshold else None,
            "invariant_source": (
                str(self.invariant_source.relative_to(self.root))
                if self.invariant_source
                else None
            ),
            "invariant_ids": list(self.invariant_ids),
            "has_project_md": self.has_project_md,
        }


def _languages(root: Path) -> tuple[str, ...]:
    found = [
        lang
        for lang, names in MANIFESTS.items()
        if any((root / n).exists() for n in names)
    ]
    return tuple(sorted(found))


def _make_targets(root: Path) -> tuple[str, ...]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return ()
    text = makefile.read_text(encoding="utf-8", errors="replace")
    skip = {".PHONY", ".DEFAULT_GOAL", ".SUFFIXES"}
    targets = [t for t in _MAKE_TARGET.findall(text) if t not in skip]
    return tuple(sorted(set(targets)))


def _threshold(root: Path) -> ThresholdSource | None:
    """Find the coverage floor. Order matters: an explicit governance policy wins."""
    policy_candidates = [
        root / "harness" / "shared" / "governance-policy.json",
        root / "governance-policy.json",
        root / ".governance" / "governance-policy.json",
    ]
    for policy in policy_candidates:
        if not policy.exists():
            continue
        try:
            data = json.loads(policy.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        coverage = data.get("coverage")
        if isinstance(coverage, dict) and isinstance(coverage.get("lines"), int):
            rel = policy.relative_to(root)
            return ThresholdSource(f"{rel}:coverage.lines", coverage["lines"])

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        match = _FAIL_UNDER.search(pyproject.read_text(encoding="utf-8", errors="replace"))
        if match:
            return ThresholdSource(
                "pyproject.toml:[tool.coverage.report].fail_under", int(match.group(1))
            )
    return None


def _invariants(root: Path) -> tuple[Path | None, tuple[str, ...]]:
    for rel in INVARIANT_SOURCES:
        path = root / rel
        if not path.exists():
            continue
        ids = sorted(
            set(_INV_ID.findall(path.read_text(encoding="utf-8", errors="replace"))),
            key=lambda s: int(s.split("-")[1]),
        )
        if ids:
            return path, tuple(ids)
    return None, ()


def detect_dialect(spec_paths: list[Path]) -> str:
    """Classify which OpenSpec spec dialect a repo writes.

    ``upstream``  -- ``## ADDED Requirements`` + ``#### Scenario:`` GIVEN/WHEN/THEN.
    ``harness``   -- ``## Acceptance Criteria`` with ``AC-<AREA>-<n>`` + ``_Verified by:_``.
    ``mixed``     -- both appear across the repo, which is itself a finding.
    ``unknown``   -- no spec files, or neither marker present.
    """
    upstream = harness = 0
    for path in spec_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "## ADDED Requirements" in text or "#### Scenario:" in text:
            upstream += 1
        if "## Acceptance Criteria" in text and re.search(r"\bAC-[A-Z]{2,}-\d+\b", text):
            harness += 1
    if upstream and harness:
        return "mixed"
    if upstream:
        return "upstream"
    if harness:
        return "harness"
    return "unknown"


def find_spec_files(openspec_root: Path) -> list[Path]:
    return sorted(openspec_root.glob("changes/*/specs/*/spec.md"))


def profile(root: Path) -> StackProfile:
    root = root.resolve()
    openspec_root = root / "openspec"
    has_openspec = openspec_root.is_dir()
    spec_files = find_spec_files(openspec_root) if has_openspec else []
    change_dirs = (
        tuple(sorted(p for p in (openspec_root / "changes").glob("*") if p.is_dir()))
        if has_openspec and (openspec_root / "changes").is_dir()
        else ()
    )
    invariant_source, invariant_ids = _invariants(root)
    return StackProfile(
        root=root,
        languages=_languages(root),
        make_targets=_make_targets(root),
        openspec_root=openspec_root if has_openspec else None,
        change_dirs=change_dirs,
        dialect=detect_dialect(spec_files),
        threshold=_threshold(root),
        invariant_source=invariant_source,
        invariant_ids=invariant_ids,
        has_project_md=(openspec_root / "project.md").exists() if has_openspec else False,
    )
