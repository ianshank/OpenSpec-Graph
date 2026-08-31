"""Dialect-neutral data model for a parsed spec.

Criterion/Requirement/ParsedSpec. The dataclasses reference the compiled
patterns from :mod:`parse_semantics` (negative detection, make/pytest
extraction, heading-drift constants) but perform no parsing themselves.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from .parse_semantics import (
    CANONICAL_REQ_LEVEL,
    CANONICAL_SCEN_LEVEL,
    MAKE_REF,
    NEGATIVE_PATTERNS,
    PYTEST_SEL,
    Waiver,
)

__all__ = ["Criterion", "ParsedSpec", "Requirement"]


@dataclasses.dataclass(frozen=True)
class Criterion:
    """A verifiable claim: a harness AC, or an upstream Scenario."""

    ident: str
    text: str
    note: str = ""
    verified_by: str = ""
    requirement_refs: tuple[str, ...] = ()
    line: int = 0

    @property
    def is_negative(self) -> bool:
        blob = f"{self.note} {self.text}"
        return any(p.search(blob) for p in NEGATIVE_PATTERNS)

    @property
    def has_stage(self) -> bool:
        return bool(MAKE_REF.search(self.verified_by))

    @property
    def has_selector(self) -> bool:
        return bool(PYTEST_SEL.search(self.verified_by)) or "·" in self.verified_by


@dataclasses.dataclass(frozen=True)
class Requirement:
    ident: str
    text: str
    kind: str  # "functional" | "constraint" | "shall"
    level: int = 0  # markdown heading depth, 0 for list-declared requirements
    body: str = ""  # upstream-dialect prose beneath the heading; "" for harness

    @property
    def is_normative(self) -> bool:
        blob = f"{self.text} {self.body}".upper()
        return any(m in blob for m in ("SHALL", "MUST"))


@dataclasses.dataclass(frozen=True)
class ParsedSpec:
    path: Path
    dialect: str
    sections: tuple[str, ...]
    status: str | None
    requirements: tuple[Requirement, ...]
    criteria: tuple[Criterion, ...]
    make_refs: tuple[str, ...]
    invariant_refs: tuple[str, ...]
    hard_coded_thresholds: tuple[str, ...]
    delta_headers: tuple[str, ...]
    scenario_levels: tuple[int, ...] = ()
    suppressed: frozenset[str] = frozenset()
    waivers: tuple[Waiver, ...] = ()
    adr_refs: tuple[str, ...] = ()
    raw: str = dataclasses.field(repr=False, default="")

    @property
    def heading_drift(self) -> tuple[str, ...]:
        """Heading depths that deviate from the upstream OpenSpec convention."""
        issues: list[str] = []
        bad_req = sorted({r.level for r in self.requirements if r.level not in (0, CANONICAL_REQ_LEVEL)})
        bad_scen = sorted({lvl for lvl in self.scenario_levels if lvl != CANONICAL_SCEN_LEVEL})
        for lvl in bad_req:
            issues.append(
                f"requirements are at H{lvl} ({'#' * lvl}), convention is "
                f"H{CANONICAL_REQ_LEVEL} (### Requirement:)"
            )
        for lvl in bad_scen:
            issues.append(
                f"scenarios are at H{lvl} ({'#' * lvl}), convention is "
                f"H{CANONICAL_SCEN_LEVEL} (#### Scenario:)"
            )
        return tuple(issues)

    @property
    def has_negative_criterion(self) -> bool:
        return any(c.is_negative for c in self.criteria)

    @property
    def orphan_requirements(self) -> tuple[str, ...]:
        """Requirements no criterion references. Shared by H003 (harness) and
        U002 (upstream) -- both dialects need exactly this computation."""
        referenced = {ref for c in self.criteria for ref in c.requirement_refs}
        return tuple(r.ident for r in self.requirements if r.ident not in referenced)
