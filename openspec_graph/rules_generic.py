"""Universal (dialect-agnostic) rules: G001-G007.

G006's real check is cross-tree (a declared invariant cited by no living
spec anywhere), so it cannot be expressed as a per-spec ``Rule.check`` --
see ``orphan_invariant_ids()`` below and ``rules.evaluate_tree()``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .detect import StackProfile
from .parse import ParsedSpec, threshold_values
from .rule_types import ERROR, GENERIC_STAGES, WARN, Rule

__all__ = ["GENERIC_RULES"]


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
    real_value = profile.threshold.value if profile.threshold else None
    for offender in spec.hard_coded_thresholds:
        if real_value is not None:
            values = threshold_values(offender)
            # Suppress only on a single, unambiguous match -- never on "the
            # real value merely appears somewhere in the line," which would
            # wrongly excuse a genuine violation sitting next to a
            # coincidentally-matching, unrelated number (e.g. a delta
            # description: "raised from 80% to 90%").
            if len(values) == 1 and values[0] == real_value:
                continue
        yield f"hard-coded threshold; read it from {locator} instead -- {offender!r}"


def _unknown_make_target(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    # No confidence-level branching needed here: detect._make_target_facts
    # already widens profile.make_targets with the regex fallback whenever
    # structural parsing is low-confidence, so this rule, graph.py, and
    # scaffold.pick_stage() all see the same, already-resolved picture of
    # "what targets exist" (AC-MP-3/AC-MP-4).
    if not profile.make_targets:
        return
    known = set(profile.make_targets)
    for target in spec.make_refs:
        if target not in known and target not in GENERIC_STAGES:
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
            yield f"references {ref}, which is not declared in {profile.invariant_source_name}"


def _unjustified_waiver(spec: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    for waiver in spec.waivers:
        if not waiver.reason:
            yield (
                f"waiver of {waiver.rule} at line {waiver.line} has no reason; "
                "a waiver is a claim that must justify itself"
            )


def orphan_invariant_ids(specs: Sequence[ParsedSpec], profile: StackProfile) -> tuple[str, ...]:
    """Declared invariants cited by no spec in ``specs``.

    A whole-tree question, not a per-spec one -- called once by
    ``rules.evaluate_tree()``, never per-spec. See that function and
    DEC-WL-001 for why no ``Rule.check`` signature can express this.
    """
    if not profile.invariant_ids:
        return ()
    cited = {ref for spec in specs for ref in spec.invariant_refs}
    return tuple(inv for inv in profile.invariant_ids if inv not in cited)


def _orphan_invariant_registry_stub(_s: ParsedSpec, _p: StackProfile) -> Iterable[str]:
    # Inert: the real cross-tree check is orphan_invariant_ids(), run once
    # per validate/graph pass by rules.evaluate_tree(), not per spec. This
    # stub exists only so `planlint rules`/`rules --json` lists G006.
    return ()


GENERIC_RULES: tuple[Rule, ...] = (
    Rule("G001", ERROR, ("*",), "spec declares verifiable criteria", _no_criteria),
    Rule("G002", ERROR, ("*",), "at least one non-success criterion", _needs_negative),
    Rule("G003", ERROR, ("*",), "no hard-coded thresholds", _hard_coded_threshold),
    Rule("G004", ERROR, ("*",), "cited make targets exist", _unknown_make_target),
    Rule("G005", WARN, ("*",), "cited invariants are declared", _unknown_invariant),
    Rule(
        "G006",
        WARN,
        ("*",),
        "declared invariants are cited by a living spec or waived",
        _orphan_invariant_registry_stub,
    ),
    Rule("G007", ERROR, ("*",), "every waiver states a reason", _unjustified_waiver),
)
