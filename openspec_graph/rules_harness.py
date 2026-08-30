"""Harness-dialect rules: H001-H006."""

from __future__ import annotations

from collections.abc import Iterable

from .detect import StackProfile
from .parse import ParsedSpec
from .rule_types import ERROR, WARN, Rule

__all__ = ["HARNESS_RULES"]


def _ac_missing_verification(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    for crit in spec.criteria:
        if not crit.verified_by:
            yield f"{crit.ident} has no `_Verified by:_` line; it is an assertion, not a criterion"
        elif not crit.has_stage:
            yield f"{crit.ident} names no `make` stage, so CI cannot run it"


def _ac_missing_requirement(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    if not spec.requirements:
        return
    for crit in spec.criteria:
        if not crit.requirement_refs:
            yield f"{crit.ident} traces to no R-/C- requirement"


def _orphan_requirement(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    for ident in spec.orphan_requirements:
        yield f"{ident} is declared but no acceptance criterion verifies it"


def _duplicate_ac(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    seen: set[str] = set()
    for crit in spec.criteria:
        if crit.ident in seen:
            yield f"duplicate criterion id {crit.ident}"
        seen.add(crit.ident)


def _blocking_question_status(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    if "(BLOCKING)" in spec.raw and spec.status not in {None, "DRAFT"}:
        yield (
            f"status is {spec.status} but the document still carries a (BLOCKING) "
            "open question"
        )


def _missing_sections(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    required = {
        "problem statement",
        "requirements",
        "acceptance criteria",
        "validation matrix",
    }
    present = {s.lower() for s in spec.sections}
    for missing in sorted(required - present):
        yield f"missing required section: {missing.title()}"


HARNESS_RULES: tuple[Rule, ...] = (
    Rule("H001", ERROR, ("harness",), "every AC is verifiable", _ac_missing_verification),
    Rule("H002", WARN, ("harness",), "every AC traces to a requirement", _ac_missing_requirement),
    Rule("H003", WARN, ("harness",), "no orphan requirements", _orphan_requirement),
    Rule("H004", ERROR, ("harness",), "criterion ids are unique", _duplicate_ac),
    Rule("H005", WARN, ("harness",), "blocking questions keep status DRAFT", _blocking_question_status),
    Rule("H006", WARN, ("harness",), "required sections present", _missing_sections),
)
