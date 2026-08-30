"""Project the spec dependency graph that `validate` already walks.

This is a pure projection, not a second analysis. The graph is built from the
same `detect.profile` and `parse.parse_spec` calls `validate` uses, and its
broken-link count is the finding count from `rules.evaluate`. The two can never
disagree by construction (R-GR-1, AC-GR-4).

Node types: ``spec``, ``requirement``, ``criterion``, ``stage``,
``invariant``. Edge types: ``traces-to`` (criterion -> requirement),
``verified-by`` (criterion -> stage), ``declares`` (spec -> invariant),
``finding`` (spec -> rule, a broken link recorded from `validate`).
"""

from __future__ import annotations

from pathlib import Path

from . import detect, parse, rules
from .detect import StackProfile

__all__ = ["NoOpenSpecTreeError", "build_graph"]


class NoOpenSpecTreeError(Exception):
    """Raised when the target has no ``openspec/`` directory to graph."""


def _stages_cited(criterion_verified_by: str) -> list[str]:
    """The make stages a criterion's `_Verified by:` line names."""
    return parse._MAKE_REF.findall(criterion_verified_by or "")


def build_graph(profile: StackProfile) -> dict:
    """Build the dependency graph for every change package under ``openspec/``.

    Raises ``NoOpenSpecTreeError`` if the target has no ``openspec/`` tree
    (AC-GR-2): the caller exits non-zero with a message naming the missing
    directory rather than emitting an empty graph.
    """
    if not profile.openspec_root or not profile.openspec_root.is_dir():
        raise NoOpenSpecTreeError(
            f"no openspec/ directory found at {profile.root}/openspec; "
            "run `specgraph init` first"
        )

    spec_files = detect.find_spec_files(profile.openspec_root)
    known_stages = set(profile.make_targets)
    known_invariants = set(profile.invariant_ids)
    dialect = profile.dialect if profile.dialect != "unknown" else "auto"

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    def add_node(node_id: str, **fields: object) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, **fields})

    broken_links = 0

    for path in spec_files:
        spec = parse.parse_spec(path, dialect)
        rel = _relative_to(path, profile.root)
        spec_node = f"spec:{rel}"
        add_node(
            spec_node,
            type="spec",
            path=rel,
            dialect=spec.dialect,
            status=spec.status,
            has_negative=spec.has_negative_criterion,
        )

        for req in spec.requirements:
            add_node(
                req.ident,
                type="requirement",
                text=req.text[:200],
                kind=req.kind,
                spec=spec_node,
            )

        for crit in spec.criteria:
            add_node(
                crit.ident,
                type="criterion",
                text=crit.text[:200],
                is_negative=crit.is_negative,
                has_stage=crit.has_stage,
                spec=spec_node,
            )
            # criterion -> requirement
            for ref in crit.requirement_refs:
                edges.append({"source": crit.ident, "target": ref, "type": "traces-to"})
            # criterion -> stage (verified-by). A stage the repo lacks is an
            # edge to a node marked exists=False (AC-GR-5).
            for stage in _stages_cited(crit.verified_by):
                exists = stage in known_stages
                stage_node = f"stage:{stage}"
                add_node(stage_node, type="stage", name=stage, exists=exists)
                edges.append(
                    {"source": crit.ident, "target": stage_node, "type": "verified-by", "exists": exists}
                )

        # spec -> invariant (declares). Undeclared invariants are edges to
        # nodes marked exists=False.
        for inv in spec.invariant_refs:
            exists = inv in known_invariants
            inv_node = f"invariant:{inv}"
            add_node(inv_node, type="invariant", name=inv, exists=exists)
            edges.append(
                {"source": spec_node, "target": inv_node, "type": "declares", "exists": exists}
            )

        # Broken links: the findings `validate` reports for this spec. Counting
        # them here guarantees the graph's broken-link total equals validate's
        # finding total (AC-GR-4).
        findings = rules.evaluate(spec, profile)
        broken_links += len(findings)
        for finding in findings:
            edges.append(
                {
                    "source": spec_node,
                    "target": finding.rule,
                    "type": "finding",
                    "broken": True,
                    "severity": finding.severity,
                    "message": finding.message,
                }
            )

    # Orphan requirements: requirement nodes with no incoming traces-to edge
    # (AC-GR-3).
    incoming_traces = {e["target"] for e in edges if e["type"] == "traces-to"}
    for node in nodes:
        if node.get("type") == "requirement" and node["id"] not in incoming_traces:
            node["orphan"] = True

    return {
        "root": str(profile.root),
        "dialect": profile.dialect,
        "specs": len(spec_files),
        "nodes": nodes,
        "edges": edges,
        "broken_links": broken_links,
        "threshold_locator": profile.threshold.locator if profile.threshold else None,
        "invariant_source": (
            str(profile.invariant_source.relative_to(profile.root))
            if profile.invariant_source
            else None
        ),
    }


def _relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
