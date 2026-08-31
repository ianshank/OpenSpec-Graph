"""Witness-mode rules: W001-W002 (CP-WM).

Evaluated only when ``--require-witness`` is passed to ``validate`` --
neither rule's ``check`` gates itself (it can't see the flag); the gate is
``cli.cmd_validate`` choosing ``rules.RULES`` vs. ``rules.NON_WITNESS_RULES``
before calling ``rules.evaluate()`` (``DEC-WM-007``). The same
``NON_WITNESS_RULES`` constant is what excludes both rules from
``graph.py``'s output entirely (``DEC-WM-013``).

Both apply to every dialect (``DEC-WM-005``): ``Criterion.verified_by``
already carries a backtick-fenced `` `make X` `` citation for harness (the
``_Verified by:_`` line) and upstream (the whole Scenario block) alike,
exactly like ``graph.py::_stages_cited()`` already relies on. A criterion
citing more than one stage (e.g. a GWT scenario mentioning both
`` `make build` `` and `` `make test` ``) requires a witness for every
citation -- no heuristic picks "the real one" (``DEC-WM-016``).
"""

from __future__ import annotations

from collections.abc import Iterable

from .detect import StackProfile
from .parse import MAKE_REF, Criterion, ParsedSpec
from .rule_types import ERROR, Rule
from .witness import matching_witnesses

__all__ = ["WITNESS_RULES"]


def _stage_citations(spec: ParsedSpec) -> Iterable[tuple[Criterion, str]]:
    for crit in spec.criteria:
        for stage in MAKE_REF.findall(crit.verified_by):
            yield crit, stage


def _missing_witness(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    """W001: distinguishes *why* a citation is unproven rather than one
    generic "no witness" message for every cause (missing, stale-commit,
    and failing-run findings would otherwise be indistinguishable to a CI
    maintainer staring at a red ``--require-witness`` run)."""
    for crit, stage in _stage_citations(spec):
        if not profile.witnesses:
            # current_sha is None here too (DEC-WM-008's lazy skip -- never
            # even attempted), but that's not why this citation is unproven:
            # nothing has ever been witnessed. Saying "sha could not be
            # determined" would misdiagnose this as a git problem.
            yield f"{crit.ident} cites `{stage}`, which has never been witnessed"
            continue
        if profile.current_sha is None:
            yield (
                f"{crit.ident} cites `{stage}`, but the current commit sha could not "
                "be determined; no witness can be verified"
            )
            continue
        at_commit = matching_witnesses(profile.witnesses, stage, profile.current_sha)
        if any(w.exit_code == 0 for w in at_commit):
            continue
        failing = next((w for w in at_commit if w.exit_code != 0), None)
        if failing is not None:
            yield (
                f"{crit.ident} cites `{stage}`, whose witness at the current commit "
                f"recorded a failing run (exit {failing.exit_code})"
            )
        elif any(w.stage == stage for w in profile.witnesses):
            yield f"{crit.ident} cites `{stage}`, which is witnessed, but not at the current commit"
        else:
            yield f"{crit.ident} cites `{stage}`, which has never been witnessed"


def _witness_below_floor(spec: ParsedSpec, profile: StackProfile) -> Iterable[str]:
    """W002: only evaluates witnesses that already clear W001's own bar
    (fresh, exit-0, at the current commit) -- a missing witness is W001's
    finding to make, not a second, redundant one here."""
    if profile.threshold is None or profile.threshold.value is None or profile.current_sha is None:
        return
    floor = profile.threshold.value
    for crit, stage in _stage_citations(spec):
        at_commit = matching_witnesses(profile.witnesses, stage, profile.current_sha)
        for w in at_commit:
            if w.exit_code != 0:
                continue
            if w.coverage is not None and w.coverage < floor:
                yield (
                    f"{crit.ident} cites `{stage}`, whose witness recorded "
                    f"{w.coverage}% coverage, below the detected floor of {floor}%"
                )


WITNESS_RULES: tuple[Rule, ...] = (
    Rule("W001", ERROR, ("*",), "every cited stage has a fresh, passing witness", _missing_witness),
    Rule("W002", ERROR, ("*",), "a witness's recorded coverage meets the detected floor", _witness_below_floor),
)
