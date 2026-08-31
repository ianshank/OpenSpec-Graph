"""Tests for mermaid.py -- the Mermaid flowchart export (CP-GV).

Pure unit tests: to_mermaid operates on a plain dict (build_graph()'s own
return shape), no CLI/subprocess needed (mirrors test_dialect_card.py's
style).
"""

from __future__ import annotations

from openspec_graph import mermaid


def _graph(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> dict[str, object]:
    return {"root": "/repo", "dialect": "harness", "specs": 1, "nodes": nodes, "edges": edges, "broken_links": 0}


def test_empty_graph_renders_a_valid_header_with_no_nodes_or_edges() -> None:
    out = mermaid.to_mermaid(_graph([], []))
    assert out.startswith("flowchart LR\n")
    assert "classDef orphan" in out
    assert "classDef missing" in out
    assert "n0" not in out


def test_node_ids_are_sanitized_to_synthetic_identifiers() -> None:
    node = {"id": "spec:openspec/changes/x/specs/y/spec.md", "type": "spec", "path": "openspec/changes/x/specs/y/spec.md"}
    out = mermaid.to_mermaid(_graph([node], []))
    assert "n0[" in out
    # the real, slash-containing id never appears as a bare Mermaid identifier
    for line in out.splitlines():
        prefix = line.strip().split("[")[0].split(" ")[0]
        assert "/" not in prefix


def test_node_label_uses_name_when_present() -> None:
    node = {"id": "stage:test", "type": "stage", "name": "test", "exists": True}
    out = mermaid.to_mermaid(_graph([node], []))
    assert 'n0["test"]' in out


def test_node_label_combines_ident_and_text_for_requirement_nodes() -> None:
    node = {"id": "R-DMO-1", "type": "requirement", "text": "The system MUST attest every write.", "kind": "functional"}
    out = mermaid.to_mermaid(_graph([node], []))
    assert 'n0["R-DMO-1: The system MUST attest every write."]' in out


def test_node_label_escapes_embedded_quotes() -> None:
    node = {"id": "R-DMO-1", "type": "requirement", "text": 'A "quoted" requirement.'}
    out = mermaid.to_mermaid(_graph([node], []))
    assert "&quot;quoted&quot;" in out
    # no unescaped quote breaks the label's own bracket syntax
    assert '"A "quoted"' not in out


def test_orphan_node_gets_the_orphan_class() -> None:
    node = {"id": "R-DMO-9", "type": "requirement", "text": "orphaned", "orphan": True}
    out = mermaid.to_mermaid(_graph([node], []))
    assert "class n0 orphan" in out


def test_missing_node_gets_the_missing_class() -> None:
    node = {"id": "stage:nope", "type": "stage", "name": "nope", "exists": False}
    out = mermaid.to_mermaid(_graph([node], []))
    assert "class n0 missing" in out


def test_orphan_takes_precedence_over_missing_when_both_would_apply() -> None:
    node = {"id": "invariant:INV-9", "type": "invariant", "name": "INV-9", "exists": True, "orphan": True}
    out = mermaid.to_mermaid(_graph([node], []))
    assert "class n0 orphan" in out
    assert "class n0 missing" not in out


def test_a_plain_edge_carries_no_link_style() -> None:
    nodes = [{"id": "AC-1", "type": "criterion"}, {"id": "R-1", "type": "requirement"}]
    edges = [{"source": "AC-1", "target": "R-1", "type": "traces-to"}]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    assert "n0 -->|traces-to| n1" in out
    assert "linkStyle" not in out


def test_a_finding_edge_gets_a_broken_link_style() -> None:
    nodes = [{"id": "spec:x", "type": "spec"}]
    edges = [{"source": "spec:x", "target": "G004", "type": "finding", "broken": True, "severity": "ERROR", "message": "m"}]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    assert "n0 -->|finding| G004" in out
    assert "linkStyle 0 stroke:#c00,stroke-width:2px;" in out


def test_an_exists_false_edge_gets_a_broken_link_style() -> None:
    nodes = [{"id": "AC-1", "type": "criterion"}, {"id": "stage:nope", "type": "stage", "name": "nope", "exists": False}]
    edges = [{"source": "AC-1", "target": "stage:nope", "type": "verified-by", "exists": False}]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    assert "linkStyle 0 stroke:#c00,stroke-width:2px;" in out


def test_link_style_index_matches_edge_declaration_order() -> None:
    nodes = [{"id": "AC-1", "type": "criterion"}, {"id": "R-1", "type": "requirement"}, {"id": "stage:nope", "type": "stage", "name": "nope", "exists": False}]
    edges = [
        {"source": "AC-1", "target": "R-1", "type": "traces-to"},
        {"source": "AC-1", "target": "stage:nope", "type": "verified-by", "exists": False},
    ]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    assert "linkStyle 1 stroke:#c00,stroke-width:2px;" in out
    assert "linkStyle 0" not in out


def test_a_rule_ident_edge_target_with_no_matching_node_is_used_verbatim() -> None:
    nodes = [{"id": "spec:x", "type": "spec"}]
    edges = [{"source": "spec:x", "target": "G004", "type": "finding", "broken": True, "severity": "ERROR", "message": "m"}]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    # G004 has no corresponding node, so it's Mermaid's own implicit-node
    # syntax: the bare, already-safe rule ident used directly as a target.
    assert "| G004" in out


def test_a_hyphenated_ident_edge_target_with_no_matching_node_is_used_verbatim() -> None:
    # Real requirement idents contain hyphens (e.g. "R-DMO-1"), unlike the
    # rule idents (e.g. "G004") the sibling test above uses -- confirming
    # the same verbatim fallback renders a hyphenated ident cleanly, not
    # just a hyphen-free one.
    nodes = [{"id": "AC-1", "type": "criterion"}]
    edges = [{"source": "AC-1", "target": "R-DMO-1", "type": "traces-to"}]
    out = mermaid.to_mermaid(_graph(nodes, edges))
    assert "n0 -->|traces-to| R-DMO-1" in out


def test_output_is_deterministic_across_repeated_calls() -> None:
    nodes = [{"id": "spec:x", "type": "spec", "path": "x"}, {"id": "AC-1", "type": "criterion", "text": "t"}]
    edges = [{"source": "spec:x", "target": "AC-1", "type": "declares", "exists": True}]
    graph = _graph(nodes, edges)
    assert mermaid.to_mermaid(graph) == mermaid.to_mermaid(graph)
