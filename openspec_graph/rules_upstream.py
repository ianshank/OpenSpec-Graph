"""Upstream-dialect rules: U001-U005."""

from __future__ import annotations

from collections.abc import Iterable

from .detect import StackProfile
from .parse import ParsedSpec, scenario_has_gwt
from .rule_types import ERROR, WARN, Rule

__all__ = ["UPSTREAM_RULES"]


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
        if not req.is_normative:
            yield f"requirement {req.text[:60]!r} uses no SHALL/MUST; it is not normative"


UPSTREAM_RULES: tuple[Rule, ...] = (
    Rule("U001", ERROR, ("upstream",), "delta header present", _missing_delta_header),
    Rule("U002", ERROR, ("upstream",), "every requirement has a scenario", _requirement_without_scenario),
    Rule("U003", ERROR, ("upstream",), "scenarios are GIVEN/WHEN/THEN", _scenario_without_gwt),
    Rule("U004", WARN, ("upstream",), "requirements are normative", _requirement_without_modal),
    Rule("U005", WARN, ("upstream",), "heading levels match convention", _heading_drift),
)
