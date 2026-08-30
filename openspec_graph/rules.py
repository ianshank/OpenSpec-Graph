"""Rule engine. Each rule turns a prose convention into a mechanical check.

Severity contract:
  ERROR -- blocks the gate. The document makes an unverifiable or false claim.
  WARN  -- degrades review quality but does not make the document wrong.
  INFO  -- observation, never blocks.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Callable, Iterable
from pathlib import Path

from .detect import StackProfile
from .parse import ParsedSpec, scenario_has_gwt

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# Make targets a spec may cite without them existing yet in the Makefile.
_GENERIC_STAGES = {"ci", "test", "validate", "lint", "coverage"}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    path: Path | None = None
    line: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "path": str(self.path) if self.path else None,
            "line": self.line,
        }

    def render(self, root: Path | None = None) -> str:
        where = ""
        if self.path:
            shown = self.path
            if root:
                with contextlib.suppress(ValueError):
                    shown = self.path.relative_to(root)
            where = f"{shown}:{self.line}: " if self.line else f"{shown}: "
        return f"{self.severity:5s} {self.rule}  {where}{self.message}"


@dataclasses.dataclass(frozen=True)
class Rule:
    ident: str
    severity: str
    dialects: tuple[str, ...]  # ("*",) for any
    summary: str
    check: Callable[[ParsedSpec, StackProfile], Iterable[str]]

    def applies(self, dialect: str) -> bool:
        return "*" in self.dialects or dialect in self.dialects


# --------------------------------------------------------------------------
# Universal rules
# --------------------------------------------------------------------------


def _no_criteria(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    if spec.criteria:
        return
    if spec.requirements:
        yield (
            f"{len(spec.requirements)} requirement(s) but no Scenario or acceptance "
            "criterion; the obligations are stated but nothing verifies them"
        )
    else:
        yield (
            "no requirements and no verifiable criteria recognized; the document "
            "uses neither the `### Requirement:`/`#### Scenario:` form nor "
            "`- [ ] **AC-<AREA>-<n>:**`, so 'done' is undefined"
        )


def _needs_negative(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    if spec.criteria and not spec.has_negative_criterion:
        yield (
            "no criterion names a non-success outcome; a plan that only describes "
            "success has not said what going wrong looks like"
        )


def _hard_coded_threshold(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    locator = profile.threshold.locator if profile.threshold else "the governance policy"
    for offender in spec.hard_coded_thresholds:
        yield f"hard-coded threshold; read it from {locator} instead -- {offender!r}"


def _unknown_make_target(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    if not profile.make_targets:
        return
    known = set(profile.make_targets)
    for target in spec.make_refs:
        if target not in known and target not in _GENERIC_STAGES:
            yield (
                f"cites `make {target}` which is not a target in the target "
                f"repo's Makefile; the criterion cannot be executed as written"
            )


def _unknown_invariant(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    if not profile.invariant_ids:
        return
    known = set(profile.invariant_ids)
    for ref in spec.invariant_refs:
        if ref not in known:
            src = (
                profile.invariant_source.name
                if profile.invariant_source
                else "the contract"
            )
            yield f"references {ref}, which is not declared in {src}"


# --------------------------------------------------------------------------
# Harness-dialect rules
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Upstream-dialect rules
# --------------------------------------------------------------------------


def _missing_delta_header(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    if not spec.delta_headers:
        yield (
            "no ADDED/MODIFIED/REMOVED Requirements header; an upstream spec delta "
            "must declare which operation it performs"
        )


def _requirement_without_scenario(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    covered = {ref for c in spec.criteria for ref in c.requirement_refs}
    for req in spec.requirements:
        if req.ident not in covered:
            yield f"requirement {req.ident!r} ({req.text[:60]}...) has no Scenario"


def _scenario_without_gwt(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    for crit in spec.criteria:
        if not scenario_has_gwt(crit):
            yield (
                f"{crit.ident} ({crit.text[:50]}...) is missing one of "
                "GIVEN/WHEN/THEN and is therefore not executable"
            )


def _heading_drift(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    yield from spec.heading_drift


def _requirement_without_modal(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    for req in spec.requirements:
        if not any(m in req.text.upper() for m in ("SHALL", "MUST")):
            yield f"requirement {req.text[:60]!r} uses no SHALL/MUST; it is not normative"


RULES: tuple[Rule, ...] = (
    Rule("G001", ERROR, ("*",), "spec declares verifiable criteria", _no_criteria),
    Rule("G002", ERROR, ("*",), "at least one non-success criterion", _needs_negative),
    Rule("G003", ERROR, ("*",), "no hard-coded thresholds", _hard_coded_threshold),
    Rule("G004", ERROR, ("*",), "cited make targets exist", _unknown_make_target),
    Rule("G005", WARN, ("*",), "cited invariants are declared", _unknown_invariant),
    Rule("H001", ERROR, ("harness",), "every AC is verifiable", _ac_missing_verification),
    Rule("H002", WARN, ("harness",), "every AC traces to a requirement", _ac_missing_requirement),
    Rule("H003", WARN, ("harness",), "no orphan requirements", _orphan_requirement),
    Rule("H004", ERROR, ("harness",), "criterion ids are unique", _duplicate_ac),
    Rule("H005", WARN, ("harness",), "blocking questions keep status DRAFT", _blocking_question_status),
    Rule("H006", WARN, ("harness",), "required sections present", _missing_sections),
    Rule("U001", ERROR, ("upstream",), "delta header present", _missing_delta_header),
    Rule("U002", ERROR, ("upstream",), "every requirement has a scenario", _requirement_without_scenario),
    Rule("U003", ERROR, ("upstream",), "scenarios are GIVEN/WHEN/THEN", _scenario_without_gwt),
    Rule("U004", WARN, ("upstream",), "requirements are normative", _requirement_without_modal),
    Rule("U005", WARN, ("upstream",), "heading levels match convention", _heading_drift),
)


def evaluate(spec: ParsedSpec, profile: StackProfile) -> list[Finding]:
    """Run every applicable rule.

    A spec may waive a rule with an inline ``<!-- specgraph:allow G003 reason -->``
    comment. Waivers are downgraded to INFO rather than dropped, so a suppression
    stays visible in the report and in CI logs.
    """
    findings: list[Finding] = []
    for rule in RULES:
        if not rule.applies(spec.dialect):
            continue
        suppressed = rule.ident in spec.suppressed
        for message in rule.check(spec, profile):
            findings.append(
                Finding(
                    rule=rule.ident,
                    severity=INFO if suppressed else rule.severity,
                    message=f"[waived] {message}" if suppressed else message,
                    path=spec.path,
                )
            )
    return findings


def rule_table() -> list[dict[str, str]]:
    return [
        {
            "id": r.ident,
            "severity": r.severity,
            "dialects": ",".join(r.dialects),
            "summary": r.summary,
        }
        for r in RULES
    ]
