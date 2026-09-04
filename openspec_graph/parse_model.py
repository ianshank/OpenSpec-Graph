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
    NORMATIVE_MODAL,
    PYTEST_SEL,
    Waiver,
    negation_matches,
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
    def negation_evidence(self) -> tuple[str, ...]:
        """Which negation patterns matched, in table order; empty if none.

        Additive and read-only: :attr:`is_negative` remains the boolean every
        existing caller (G002, ``graph.py``'s node attributes) uses. This
        exists so a G002 finding can be argued with -- "which word made this
        count?" previously had no answer short of re-deriving the regex list
        by hand, and the answer is what tells an author whether the rule
        agreed with them for the right reason.
        """
        return negation_matches(self.note, self.text)

    @property
    def is_negative(self) -> bool:
        return bool(self.negation_evidence)

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
        """Whether this requirement uses SHALL/MUST, on word boundaries.

        Word-bounded rather than a substring test: "shallow", "Marshalling"
        and "mustard" contain SHALL/MUST and used to make a non-normative
        requirement read as normative, which silently switched U004 off for
        it. See ``parse_semantics.NORMATIVE_MODAL``.
        """
        return bool(NORMATIVE_MODAL.search(f"{self.text} {self.body}"))


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
    raw: str = dataclasses.field(repr=False, default="")
    # Appended strictly after `raw`, not before: ParsedSpec is publicly
    # exported, and inserting a new field ahead of an existing one shifts
    # every later field's positional index -- a caller passing `raw`
    # positionally would silently bind it to this field instead (Copilot
    # review finding on PR #13). Every new field must go after the
    # previous last field, never between existing ones.
    adr_refs: tuple[str, ...] = ()

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
