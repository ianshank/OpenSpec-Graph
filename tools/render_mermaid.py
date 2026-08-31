"""Render a saved ``graph --format json`` file as a Mermaid flowchart.

A thin, separate consumer of the JSON graph, per docs/next-steps.md's own
guidance -- kept out of the core `graph` projection. `planlint graph
--format mermaid` covers the common case directly; this script covers the
other real one: rendering an artifact saved from a previous run (e.g. a CI
job's uploaded `spec-graph.json`) without re-running `planlint` at all.

Unlike every other tools/ gate script, this one imports openspec_graph --
deliberately: it exists purely to expose mermaid.to_mermaid() for this one
use case, and duplicating that function's logic here would be exactly the
kind of two-copies-drift-apart problem this project's own rules elsewhere
exist to catch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openspec_graph.mermaid import to_mermaid


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: render_mermaid.py <graph.json>", file=sys.stderr)
        return 2
    graph_path = Path(argv[1])
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    print(to_mermaid(graph), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
