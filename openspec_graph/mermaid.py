"""Mermaid flowchart export of the dependency graph (CP-GV).

Pure, stdlib-only, zero intra-package import -- mirrors ``dialect_card.py``'s
precedent. Takes exactly ``graph.build_graph()``'s existing return dict;
never touches its shape, so the golden-fixture hash locking that output
stays valid untouched by this module's existence.
"""

from __future__ import annotations

from typing import cast

__all__ = ["to_mermaid"]

# Named (not inline literals, mirroring graph.py's own NODE_TEXT_LIMIT
# precedent "so tests can reason about it"): an orphan node's stroke and a
# broken edge's linkStyle intentionally share one color -- both flag
# "something's wrong" -- so the two can't independently drift apart. A
# missing node gets a distinct, non-alert gray + dash style instead (a
# different fact: "not found," not "broken").
ALERT_COLOR = "#c00"
ORPHAN_FILL = "#fdd"
ORPHAN_TEXT = "#900"
MISSING_FILL = "#eee"
MISSING_STROKE = "#999"


def _label(node: dict[str, object]) -> str:
    # Real node ids (e.g. "spec:openspec/changes/x/specs/y/spec.md") contain
    # slashes/dots -- invalid Mermaid identifiers, so callers never use them
    # directly; this only builds the human-readable *label* text. Quotes are
    # escaped so a requirement/criterion's own free-text can't break the
    # diagram's syntax.
    ident = str(node["id"])
    text = node.get("text")
    label = f"{ident}: {text}" if text else str(node.get("name") or node.get("path") or ident)
    return label.replace('"', "&quot;")


def to_mermaid(graph: dict[str, object]) -> str:
    """Render ``build_graph()``'s dict as a Mermaid ``flowchart`` diagram.

    Every node gets a synthetic id (``n0``, ``n1``, ...); the real
    path/ident/name becomes the quoted label. Orphan and missing (``exists:
    False``) nodes get a distinct node class; broken (``exists: False`` or
    ``finding``) edges get a distinct ``linkStyle`` -- spotting a broken
    link visually, without reading JSON, is the entire point of a picture.
    """
    nodes = cast("list[dict[str, object]]", graph.get("nodes", []))
    edges = cast("list[dict[str, object]]", graph.get("edges", []))
    synthetic = {node["id"]: f"n{i}" for i, node in enumerate(nodes)}

    lines = [
        "flowchart LR",
        f"    classDef orphan fill:{ORPHAN_FILL},stroke:{ALERT_COLOR},color:{ORPHAN_TEXT};",
        f"    classDef missing fill:{MISSING_FILL},stroke:{MISSING_STROKE},stroke-dasharray: 3 3;",
        "",
    ]
    for node in nodes:
        nid = synthetic[node["id"]]
        lines.append(f'    {nid}["{_label(node)}"]')
        if node.get("orphan"):
            lines.append(f"    class {nid} orphan")
        elif node.get("exists") is False:
            lines.append(f"    class {nid} missing")

    lines.append("")
    link_styles: list[str] = []
    for i, edge in enumerate(edges):
        source = synthetic.get(edge["source"], edge["source"])
        target = synthetic.get(edge["target"], edge["target"])
        lines.append(f"    {source} -->|{edge['type']}| {target}")
        if edge.get("broken") or edge.get("exists") is False:
            link_styles.append(f"    linkStyle {i} stroke:{ALERT_COLOR},stroke-width:2px;")
    lines.extend(link_styles)

    return "\n".join(lines) + "\n"
