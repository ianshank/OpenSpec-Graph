# Change: Add Graph Export

## Why

`planlint validate` reports broken links as text, but the dependency graph it
walks is never exposed. A consumer that wants to render the spec graph, feed it
to a review dashboard, or diff it between changes has nothing to read — the
graph exists only transiently inside `rules.evaluate`.

**Evidence:** `openspec_graph/rules.py::evaluate` builds `Finding` records from a
`ParsedSpec`, but `ParsedSpec`'s `requirements`, `criteria`, `make_refs`, and
`invariant_refs` are never serialized. No CLI verb produces structured output of
the graph, only of violations.

## What Changes

- Add a `planlint graph` verb emitting the spec dependency graph as JSON
  (nodes: requirements, criteria, stages, invariants; edges: traces-to,
  verified-by, declares, gates).
- Reuse the existing `detect.profile` and `parse.parse_spec` — no new parsing.
- The graph is a pure projection of what `validate` already computes, so the two
  can never disagree.

## Non-Goals

- No visualization rendering (DOT/SVG). JSON only; rendering is a downstream
  concern.
- No new rules. `graph` is read-only projection.
- No claim of completeness for repos with no `openspec/` tree — `graph` exits
  non-zero with a clear message in that case.

## Affected Capabilities

- `graph-export`
