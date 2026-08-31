# Change: Add Mermaid Graph Export (CP-GV)

## Why

`planlint graph --format json` computes the full dependency graph (requirements,
criteria, stages, invariants, and the edges between them, including broken
links), but nothing renders it. A reviewer or architect who wants to *see* a
change's structure has to read raw JSON by hand.

**Evidence:** `openspec_graph/graph.py::build_graph` returns a plain
`nodes`/`edges` dict; no CLI verb turns it into anything a human looks at
directly. `cli.py`'s `cmd_graph` already rejects `--format dot` explicitly
(`AC-GR-6`) as a downstream, out-of-scope concern — but `docs/next-steps.md`
item 2 names a specific, narrower path forward: "a thin renderer that consumes
the JSON graph; keep it out of the core projection."

This proposal went through an adversarial review round before implementation
(mirroring this project's own established discipline for higher-risk work —
see CP-4's own two-round history). The review found and fixed a real bug in
the first design before any code was written: naively scoping `--change`
rendering would also have scoped the whole-tree orphan-invariant check,
reproducing the exact false-positive bug `cmd_validate --change` was built to
avoid (`DEC-WL-003`). Resolved in the Decisions below.

## What Changes

- `graph --format mermaid`: a new format alongside `json`, rendering the same
  graph as a Mermaid flowchart. Real node ids (which contain slashes/dots) are
  sanitized to synthetic identifiers; orphan and missing nodes, and broken
  edges, are styled distinctly.
- `graph --change <name>`: scopes which specs are rendered as nodes/edges — a
  capability `validate` already has that `graph` didn't.
- New pure module `openspec_graph/mermaid.py` (`to_mermaid(graph: dict) -> str`),
  stdlib-only, taking exactly `build_graph()`'s existing return shape.
- Companion `tools/render_mermaid.py`: renders a previously-saved
  `graph --format json` artifact (e.g. from a CI upload) without re-running
  `planlint`.
- `detect.filter_by_change()`: the `--change` path filter, previously inline
  only in `cmd_validate`, extracted and now shared by both verbs.

## Non-Goals

- **No image rendering (SVG/PNG).** Mermaid text only — the same posture as
  the existing JSON output; `planlint` still performs no rendering itself.
  `AC-GR-6`'s `--format dot` rejection is unrevised, only added to.
- **No new rules.** `graph` stays a read-only projection of what `validate`
  already computes.

## Affected Capabilities

- `mermaid-graph-export`
