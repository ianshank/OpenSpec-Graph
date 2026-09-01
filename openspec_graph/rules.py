"""Rule engine. Each rule turns a prose convention into a mechanical check.

Decomposed into focused modules; this file is the facade/registry:

- :mod:`rule_types` — ``Finding``/``Rule`` dataclasses, severity constants.
- :mod:`rules_generic` — universal rules G001-G009.
- :mod:`rules_harness` — harness-dialect rules H001-H006.
- :mod:`rules_upstream` — upstream-dialect rules U001-U005.
- :mod:`rules_speckit` — speckit-dialect rules S001-S004.
- :mod:`rules_witness` — witness-mode rules W001-W002, evaluated only under
  ``--require-witness`` (``NON_WITNESS_RULES``/``evaluate(rule_set=...)``).

Public surface (``Finding``, ``Rule``, ``evaluate``, ``rule_table``, ``RULES``,
``NON_WITNESS_RULES``, ``ERROR``/``WARN``/``INFO``) is re-exported here so
existing ``from openspec_graph.rules import ...`` imports keep working
(R-DG-1).

Severity contract:
  ERROR -- blocks the gate. The document makes an unverifiable or false claim.
  WARN  -- degrades review quality but does not make the document wrong.
  INFO  -- observation, never blocks.
"""

from __future__ import annotations

from collections.abc import Sequence

from . import rules_generic
from .detect import StackProfile
from .parse import ParsedSpec
from .rule_types import ERROR, INFO, WARN, Finding, Rule
from .rules_generic import GENERIC_RULES
from .rules_harness import HARNESS_RULES
from .rules_speckit import SPECKIT_RULES
from .rules_upstream import UPSTREAM_RULES
from .rules_witness import WITNESS_RULES

__all__ = [
    "ERROR",
    "INFO",
    "NON_WITNESS_RULES",
    "RULES",
    "WARN",
    "Finding",
    "Rule",
    "evaluate",
    "evaluate_tree",
    "rule_table",
]

# Every rule except W001/W002 -- the set graph.py always evaluates against
# (witnesses get no graph representation and no broken_links contribution,
# ever, DEC-WM-013) and cmd_validate falls back to when --require-witness
# isn't set (DEC-WM-007). Declared before RULES so RULES can build on it.
NON_WITNESS_RULES: tuple[Rule, ...] = GENERIC_RULES + HARNESS_RULES + UPSTREAM_RULES + SPECKIT_RULES
RULES: tuple[Rule, ...] = NON_WITNESS_RULES + WITNESS_RULES

# G007 (a waiver must state a reason) cannot be silenced by naming itself in
# a reason-less waiver -- that would let the enforcement rule trivially
# suppress its own violation report.
_NON_WAIVABLE = frozenset({"G007"})


def evaluate(spec: ParsedSpec, profile: StackProfile, rule_set: Sequence[Rule] = NON_WITNESS_RULES) -> list[Finding]:
    """Run every applicable rule in ``rule_set``.

    ``rule_set`` defaults to ``NON_WITNESS_RULES`` -- W001/W002 are opt-in
    (``--require-witness``), so a caller that doesn't know or care about
    witness mode (every pre-CP-WM call site, most of this project's own
    test suite) gets exactly its old behavior unchanged, not a new,
    unrequested ERROR finding sprung on it. Pass ``RULES`` explicitly to
    also evaluate W001/W002 -- the mechanism ``cmd_validate``'s
    ``--require-witness`` gate uses (``DEC-WM-007``). A spec may waive a
    rule with an inline ``<!-- specgraph:allow G003 reason -->`` comment.
    Waivers are downgraded to INFO rather than dropped, so a suppression
    stays visible in the report and in CI logs. G007 is exempt
    (_NON_WAIVABLE).
    """
    findings: list[Finding] = []
    for rule in rule_set:
        if not rule.applies(spec.dialect):
            continue
        suppressed = rule.ident in spec.suppressed and rule.ident not in _NON_WAIVABLE
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


def evaluate_tree(specs: Sequence[ParsedSpec], profile: StackProfile) -> list[Finding]:
    """Whole-tree rules no per-spec ``Rule.check`` can express (DEC-WL-001).

    G006 (a declared invariant cited by no living spec) and G009 (the same
    shape for ADRs, DEC-AD-003) -- two parallel blocks, not a registry; see
    DEC-AD-003 for why generalizing this into a dynamic dispatch mechanism
    isn't warranted for two instances. Called once per ``validate``/``graph``
    run after every living spec is parsed -- not once per spec, unlike
    ``evaluate()``. Every ``Finding`` here sets ``path=`` to the entity's own
    declaring source (``profile.invariant_source``/``profile.adr_source``)
    rather than a spec's own path, since there is no single owning spec;
    leaving ``path`` unset would default it to ``None``, and
    ``cmd_validate``'s text renderer sorts by ``(str(f.path), f.rule)`` --
    ``str(None) == "None"`` sorts before every real path, silently jumping
    the finding to the top (DEC-WL-004).
    """
    findings: list[Finding] = []

    waived_invariant = any("G006" in spec.suppressed for spec in specs)
    for inv_id in rules_generic.orphan_invariant_ids(specs, profile):
        message = f"{inv_id} is declared in {profile.invariant_source_name} but cited by no living spec"
        findings.append(
            Finding(
                rule="G006",
                severity=INFO if waived_invariant else WARN,
                message=f"[waived] {message}" if waived_invariant else message,
                path=profile.invariant_source,
                subject=inv_id,
            )
        )

    waived_adr = any("G009" in spec.suppressed for spec in specs)
    for adr_id in rules_generic.orphan_adr_ids(specs, profile):
        message = f"{adr_id} is declared in {profile.adr_source_name} but cited by no living spec"
        findings.append(
            Finding(
                rule="G009",
                severity=INFO if waived_adr else WARN,
                message=f"[waived] {message}" if waived_adr else message,
                path=profile.adr_source,
                subject=adr_id,
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
