"""Project the spec dependency graph that `validate` already walks.

This is a pure projection, not a second analysis. The graph is built from the
same `detect.profile` and `parse.parse_spec` calls `validate` uses, and its
broken-link count is the finding count from `rules.evaluate`. The two can never
disagree by construction (R-GR-1, AC-GR-4) for a default (no `--require-witness`)
run -- `graph` always evaluates `rules.NON_WITNESS_RULES`, never W001/W002, under
any flag (`graph` has no `--require-witness` of its own), so `validate
--require-witness`'s finding count can legitimately exceed `graph`'s
`broken_links`, a documented exception mirroring the existing `--change`
one for G006/G009 (`DEC-WM-013`).

Node types: ``spec``, ``requirement``, ``criterion``, ``stage``,
``invariant``, ``adr``. Edge types: ``traces-to`` (criterion -> requirement),
``verified-by`` (criterion -> stage), ``declares`` (spec -> invariant or
spec -> adr), ``finding`` (spec -> rule, or entity -> rule for a tree-scoped
finding -- a broken link recorded from `validate`). Witnesses (CP-WM) get no
node/edge type at all, ever.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from . import detect, parse, rules
from .detect import StackProfile
from .parse import ParsedSpec

__all__ = ["NoOpenSpecTreeError", "build_graph"]

# Truncate node text in the exported graph so a single verbose requirement or
# criterion cannot bloat the JSON contract. Named (not a magic number) so the
# graph-diff and golden-fixture tests can reason about it.
NODE_TEXT_LIMIT = 200


class NoOpenSpecTreeError(Exception):
    """Raised when the target has no ``openspec/`` directory to graph."""


def _stages_cited(criterion_verified_by: str) -> list[str]:
    """The make stages a criterion's `_Verified by:` line names."""
    return parse.MAKE_REF.findall(criterion_verified_by or "")


def _add_node(nodes: list[dict[str, object]], seen: set[str], node_id: str, **fields: object) -> None:
    if node_id in seen:
        return
    seen.add(node_id)
    nodes.append({"id": node_id, **fields})


def _add_spec_node(nodes: list[dict[str, object]], seen: set[str], spec: ParsedSpec, rel: str) -> str:
    spec_node = f"spec:{rel}"
    _add_node(
        nodes, seen, spec_node,
        type="spec",
        path=rel,
        dialect=spec.dialect,
        status=spec.status,
        has_negative=spec.has_negative_criterion,
    )
    return spec_node


def _entity_node_id(spec: ParsedSpec, spec_node: str, ident: str) -> str:
    """Graph node id for a requirement/criterion belonging to ``spec``.

    Harness/upstream idents are already spec-unique by authoring convention
    (e.g. ``R-DMO-1``, ``AC-DMO-1`` -- the capability abbreviation is folded
    into the id itself), so they pass through unqualified: changing this
    would re-pin every existing golden-hash graph fixture for zero benefit.
    SpecKit's own canonical convention restarts numbering at ``FR-001``/
    ``SC-001`` in *every* feature, so a repo with more than one feature
    would otherwise silently collapse the second feature's requirement/
    criterion nodes into the first's via ``_add_node``'s seen-id dedup --
    scoping the qualification to ``spec.dialect == "speckit"`` fixes the
    real collision without touching either existing dialect's node ids.
    """
    if spec.dialect == "speckit":
        return f"{spec_node}::{ident}"
    return ident


def _add_requirement_nodes(
    nodes: list[dict[str, object]], seen: set[str], spec: ParsedSpec, spec_node: str
) -> None:
    for req in spec.requirements:
        _add_node(
            nodes, seen, _entity_node_id(spec, spec_node, req.ident),
            type="requirement",
            text=req.text[:NODE_TEXT_LIMIT],
            kind=req.kind,
            spec=spec_node,
        )


def _add_criterion_nodes(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
    spec: ParsedSpec,
    spec_node: str,
    known_stages: set[str],
) -> None:
    for crit in spec.criteria:
        crit_node = _entity_node_id(spec, spec_node, crit.ident)
        _add_node(
            nodes, seen, crit_node,
            type="criterion",
            text=crit.text[:NODE_TEXT_LIMIT],
            is_negative=crit.is_negative,
            has_stage=crit.has_stage,
            spec=spec_node,
        )
        # criterion -> requirement
        for ref in crit.requirement_refs:
            req_node = _entity_node_id(spec, spec_node, ref)
            edges.append({"source": crit_node, "target": req_node, "type": "traces-to"})
        # criterion -> stage (verified-by). A stage the repo lacks is an
        # edge to a node marked exists=False (AC-GR-5).
        for stage in _stages_cited(crit.verified_by):
            exists = stage in known_stages
            stage_node = f"stage:{stage}"
            _add_node(nodes, seen, stage_node, type="stage", name=stage, exists=exists)
            edges.append(
                {"source": crit_node, "target": stage_node, "type": "verified-by", "exists": exists}
            )


def _add_invariant_edges(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
    spec: ParsedSpec,
    spec_node: str,
    known_invariants: set[str],
) -> None:
    # spec -> invariant (declares). Undeclared invariants are edges to
    # nodes marked exists=False.
    for inv in spec.invariant_refs:
        exists = inv in known_invariants
        inv_node = f"invariant:{inv}"
        _add_node(nodes, seen, inv_node, type="invariant", name=inv, exists=exists)
        edges.append(
            {"source": spec_node, "target": inv_node, "type": "declares", "exists": exists}
        )


def _add_adr_edges(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
    spec: ParsedSpec,
    spec_node: str,
    known_adrs: set[str],
) -> None:
    # spec -> adr (declares). Undeclared ADRs are edges to nodes marked
    # exists=False. Mirrors _add_invariant_edges() exactly (DEC-AD-005).
    for adr in spec.adr_refs:
        exists = adr in known_adrs
        adr_node = f"adr:{adr}"
        _add_node(nodes, seen, adr_node, type="adr", name=adr, exists=exists)
        edges.append(
            {"source": spec_node, "target": adr_node, "type": "declares", "exists": exists}
        )


def _add_finding_edges(edges: list[dict[str, object]], spec_node: str, findings: list[rules.Finding]) -> int:
    # Broken links: the findings `validate` reports for this spec. Counting
    # them here guarantees the graph's broken-link total equals validate's
    # finding total (AC-GR-4).
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
    return len(findings)


# Node "type" to synthesize for a tree-scoped finding's subject, keyed by
# the rule that produced it. Extend this mapping when a third whole-tree
# orphan check arrives (DEC-AD-005) -- not a general plugin mechanism, just
# the two-entry literal this project already uses this shape for elsewhere
# (_COMPARABLE_FIELDS, ALLOWED_VERBS).
_TREE_FINDING_NODE_KIND: dict[str, str] = {"G006": "invariant", "G009": "adr"}


def _add_tree_finding_edges(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    seen: set[str],
    findings: list[rules.Finding],
) -> int:
    # Tree-level findings (G006, G009) are about an entity in the tree --
    # an invariant or ADR, named by finding.subject -- not one spec, so
    # there is no spec_node to hang the edge off of like _add_finding_edges
    # does. _add_invariant_edges/_add_adr_edges only ever create a node for
    # an entity some spec actually cites; an orphan by definition never
    # gets one there, so this must create the node explicitly or the edge
    # below would point at a node that was never added (AC-GR-4).
    for finding in findings:
        kind = _TREE_FINDING_NODE_KIND.get(finding.rule, "unknown")
        entity_node = f"{kind}:{finding.subject}"
        _add_node(nodes, seen, entity_node, type=kind, name=finding.subject, exists=True, orphan=True)
        edges.append(
            {
                "source": entity_node,
                "target": finding.rule,
                "type": "finding",
                "broken": True,
                "severity": finding.severity,
                "message": finding.message,
            }
        )
    return len(findings)


def _mark_orphan_requirements(
    nodes: list[dict[str, object]], edges: list[dict[str, object]], untraceable_specs: set[str]
) -> None:
    # Orphan requirements: requirement nodes with no incoming traces-to edge
    # (AC-GR-3). Skipped for a spec in `untraceable_specs` -- speckit's own
    # grammar has no FR<->SC citation convention at all (C-SK-3/DEC-SK-016),
    # so every one of its requirement nodes would otherwise be marked
    # orphan unconditionally, a false "nothing traces to this" signal for a
    # dialect that was never expected to have any traces-to edges in the
    # first place. Harness/upstream are unaffected: neither spec ever adds
    # its own spec_node to `untraceable_specs`.
    incoming_traces = {e["target"] for e in edges if e["type"] == "traces-to"}
    for node in nodes:
        if node.get("type") != "requirement" or node["id"] in incoming_traces:
            continue
        if node.get("spec") in untraceable_specs:
            continue
        node["orphan"] = True


def build_graph(profile: StackProfile, spec_files: Sequence[Path] | None = None) -> dict[str, object]:
    """Build the dependency graph for every change package under ``openspec/``
    and/or every feature under a SpecKit ``specs/`` tree — whichever root(s)
    the profile has.

    Raises ``NoOpenSpecTreeError`` if the target has neither an ``openspec/``
    tree nor a SpecKit ``specs/`` tree (AC-GR-2/AC-SK-21): the caller exits
    non-zero with a message naming the missing director(y/ies) rather than
    emitting an empty graph.

    Propagates ``parse.SpecReadError`` when a discovered spec exists but its
    bytes cannot be read (AC-RE-1). Deliberately not caught here: this module
    sits below the CLI and does not own exit codes, and swallowing it would
    emit a graph that silently omits a spec it could not read -- the same
    "passed a gate that never saw it" lie the read guard exists to prevent.
    ``cmd_graph`` catches it beside ``NoOpenSpecTreeError`` and exits 2.

    ``spec_files``, if given (e.g. ``--change``-filtered), scopes which specs
    get rendered as nodes/edges -- but never what feeds
    ``rules.evaluate_tree()``, which always sees the full, unscoped tree
    regardless. Scoping that too would reproduce the exact false-positive-
    orphan bug ``cmd_validate --change`` already guards against (DEC-WL-003):
    an invariant cited only outside the rendered scope would wrongly look
    orphaned. Unlike ``cmd_validate``, which skips G006 entirely under
    ``--change``, the tree-level check still runs here and its (correctly
    unscoped) findings are still included -- an orphan invariant is, by
    definition, cited by no living spec anywhere, so it isn't "content
    belonging to a different change" being leaked into a scoped picture.
    """
    has_openspec = bool(profile.openspec_root and profile.openspec_root.is_dir())
    has_speckit = bool(profile.speckit_root and profile.speckit_root.is_dir())
    if not has_openspec and not has_speckit:
        raise NoOpenSpecTreeError(
            f"no openspec/ directory found at {profile.root / 'openspec'} and no "
            f"SpecKit specs/ tree found at {profile.root / 'specs'}; run `planlint init` first"
        )

    all_spec_files: list[Path] = []
    if profile.openspec_root and has_openspec:
        all_spec_files.extend(detect.find_spec_files(profile.openspec_root))
    if profile.speckit_root and has_speckit:
        all_spec_files.extend(detect.find_speckit_spec_files(profile.speckit_root))
    render_paths = set(all_spec_files) if spec_files is None else set(spec_files)
    known_stages = set(profile.make_targets)
    known_invariants = set(profile.invariant_ids)
    known_adrs = set(profile.adr_ids)
    dialect = profile.dialect if profile.dialect != "unknown" else "auto"

    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    seen_nodes: set[str] = set()
    broken_links = 0
    all_specs: list[ParsedSpec] = []
    rendered = 0
    untraceable_specs: set[str] = set()

    for path in all_spec_files:
        spec = parse.parse_spec(path, dialect)
        all_specs.append(spec)
        if path not in render_paths:
            continue
        rendered += 1
        rel = _relative_to(path, profile.root)
        spec_node = _add_spec_node(nodes, seen_nodes, spec, rel)
        if spec.dialect == "speckit":
            untraceable_specs.add(spec_node)
        _add_requirement_nodes(nodes, seen_nodes, spec, spec_node)
        _add_criterion_nodes(nodes, edges, seen_nodes, spec, spec_node, known_stages)
        _add_invariant_edges(nodes, edges, seen_nodes, spec, spec_node, known_invariants)
        _add_adr_edges(nodes, edges, seen_nodes, spec, spec_node, known_adrs)
        # Witness findings (W001/W002) never get graph representation and
        # never contribute to broken_links, under any flag -- NON_WITNESS_RULES
        # is the same mechanism cmd_validate's --require-witness gate uses,
        # not a second one to maintain (DEC-WM-007/DEC-WM-013).
        witness_free = rules.evaluate(spec, profile, rules.NON_WITNESS_RULES)
        broken_links += _add_finding_edges(edges, spec_node, witness_free)

    broken_links += _add_tree_finding_edges(
        nodes, edges, seen_nodes, rules.evaluate_tree(all_specs, profile)
    )

    _mark_orphan_requirements(nodes, edges, untraceable_specs)

    return {
        "root": str(profile.root),
        "dialect": profile.dialect,
        "specs": rendered,
        "nodes": nodes,
        "edges": edges,
        "broken_links": broken_links,
        "threshold_locator": profile.threshold.locator if profile.threshold else None,
        "invariant_source": (
            detect.to_posix_relative(profile.invariant_source, profile.root)
            if profile.invariant_source
            else None
        ),
        "adr_source": (
            detect.to_posix_relative(profile.adr_source, profile.root)
            if profile.adr_source
            else None
        ),
    }


def _relative_to(path: Path, root: Path) -> str:
    # Thin wrapper kept so this name stays importable (tests/test_enterprise.py
    # imports it directly) -- the real, shared logic lives in
    # detect.to_posix_relative, which every other module with this exact
    # pattern also calls.
    return detect.to_posix_relative(path, root)
