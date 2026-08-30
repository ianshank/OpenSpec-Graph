"""Rule engine. Each rule turns a prose convention into a mechanical check.

Decomposed into focused modules; this file is the facade/registry:

- :mod:`rule_types` — ``Finding``/``Rule`` dataclasses, severity constants.
- :mod:`rules_generic` — universal rules G001-G005.
- :mod:`rules_harness` — harness-dialect rules H001-H006.
- :mod:`rules_upstream` — upstream-dialect rules U001-U005.

Public surface (``Finding``, ``Rule``, ``evaluate``, ``rule_table``, ``RULES``,
``ERROR``/``WARN``/``INFO``) is re-exported here so existing
``from openspec_graph.rules import ...`` imports keep working (R-DG-1).

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
from .rules_upstream import UPSTREAM_RULES

__all__ = [
    "ERROR",
    "INFO",
    "RULES",
    "WARN",
    "Finding",
    "Rule",
    "evaluate",
    "evaluate_tree",
    "rule_table",
]

RULES: tuple[Rule, ...] = GENERIC_RULES + HARNESS_RULES + UPSTREAM_RULES

# G007 (a waiver must state a reason) cannot be silenced by naming itself in
# a reason-less waiver -- that would let the enforcement rule trivially
# suppress its own violation report.
_NON_WAIVABLE = frozenset({"G007"})


def evaluate(spec: ParsedSpec, profile: StackProfile) -> list[Finding]:
    """Run every applicable rule.

    A spec may waive a rule with an inline ``<!-- specgraph:allow G003 reason -->``
    comment. Waivers are downgraded to INFO rather than dropped, so a suppression
    stays visible in the report and in CI logs. G007 is exempt (_NON_WAIVABLE).
    """
    findings: list[Finding] = []
    for rule in RULES:
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

    Currently just G006 (a declared invariant cited by no living spec).
    Called once per ``validate``/``graph`` run after every living spec is
    parsed -- not once per spec, unlike ``evaluate()``. Every ``Finding``
    here sets ``path=profile.invariant_source`` rather than a spec's own
    path, since there is no single owning spec; leaving ``path`` unset
    would default it to ``None``, and ``cmd_validate``'s text renderer
    sorts by ``(str(f.path), f.rule)`` -- ``str(None) == "None"`` sorts
    before every real path, silently jumping G006 to the top (DEC-WL-004).
    """
    findings: list[Finding] = []
    waived = any("G006" in spec.suppressed for spec in specs)
    src = profile.invariant_source.name if profile.invariant_source else "the contract"
    for inv_id in rules_generic.orphan_invariant_ids(specs, profile):
        message = f"{inv_id} is declared in {src} but cited by no living spec"
        findings.append(
            Finding(
                rule="G006",
                severity=INFO if waived else WARN,
                message=f"[waived] {message}" if waived else message,
                path=profile.invariant_source,
                subject=inv_id,
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
