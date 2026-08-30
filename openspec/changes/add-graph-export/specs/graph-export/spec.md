# Spec: Graph Export

> **Change:** `add-graph-export`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`specgraph validate` reports broken links as text findings, but the dependency
graph it walks — requirements linked to the criteria that verify them, criteria
linked to the build stage that runs them, invariants linked to the contract that
declares them — is never exposed in a machine-readable form.

**Evidence:** `openspec_graph/rules.py::evaluate` consumes a `ParsedSpec` and
emits `Finding` records, but `ParsedSpec.requirements`, `ParsedSpec.criteria`,
`ParsedSpec.make_refs`, and `ParsedSpec.invariant_refs` are never serialized.
No CLI verb produces structured output of the graph itself, only of violations.

---

## Requirements

- R-GR-1: The system MUST emit the spec dependency graph as JSON, as a pure
  projection of what `validate` already computes, so the two cannot disagree.
- R-GR-2: The system MUST surface a broken link — an orphan requirement, a
  criterion citing a stage the repo lacks, an invariant cited but undeclared —
  as an edge to nothing in the graph, not only as a textual finding.
- C-GR-1: The change MUST NOT introduce a new parser. It MUST reuse
  `detect.profile`, `detect.find_spec_files`, and `parse.parse_spec`.
- C-GR-2: Coverage for the new module MUST meet the floor declared in
  `pyproject.toml:[tool.coverage.report].fail_under`. No literal threshold may
  appear in this spec or its tests.

## Acceptance Criteria

- [ ] **AC-GR-1:** `specgraph graph --target <repo> --format json` emits a JSON
  object with `nodes` and `edges` arrays covering every parsed spec in the
  target's `openspec/` tree. (R-GR-1)
  _Verified by:_ `pytest -k test_graph_emits_nodes_and_edges` · stage: `make validate`

- [ ] **AC-GR-2 (non-success):** Given a repo with no `openspec/` tree,
  `specgraph graph` exits non-zero and names the missing directory, rather than
  emitting an empty graph and a zero exit. (R-GR-2)
  _Verified by:_ `pytest -k test_graph_rejects_missing_tree` · stage: `make validate`

- [ ] **AC-GR-3 (non-success):** An orphan requirement — one no criterion
  references — appears in the graph as a node with no incoming `traces-to`
  edge, and the edge set is empty for that node. (R-GR-2)
  _Verified by:_ `pytest -k test_graph_surfaces_orphan_requirement` · stage: `make validate`

- [ ] **AC-GR-4:** The graph is a pure projection: for every repo where
  `validate` reports N findings, `graph` reports the same N broken links in its
  edge set, with no disagreement. (R-GR-1, C-GR-1)
  _Verified by:_ `pytest -k test_graph_matches_validate_findings` · stage: `make validate`

- [ ] **AC-GR-5:** A criterion citing a `make` stage the target repo lacks
  appears in the graph as an edge to a stage node that does not exist in the
  detected `make_targets`. (R-GR-2)
  _Verified by:_ `pytest -k test_graph_surfaces_unknown_stage` · stage: `make validate`

- [ ] **AC-GR-6:** The `--format dot` option is rejected with a non-zero exit and
  a message naming rendering as a downstream, out-of-scope concern. (C-GR-1)
  _Verified by:_ `pytest -k test_graph_rejects_dot_format` · stage: `make validate`

- [ ] **AC-GR-7:** New module coverage meets the floor declared in
  `pyproject.toml:[tool.coverage.report].fail_under`. (C-GR-2)
  _Verified by:_ `pytest -k test_graph` · stage: `make ci`

## Invariants Touched

- None. This change is additive and read-only: it projects the graph `validate`
  already walks, without altering detection, parsing, or rule evaluation.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Spec gate | `make validate` | AC-GR-1..6 pass; this spec itself validates clean |
| Full pipeline | `make ci` | all of the above, plus coverage floor met (AC-GR-7) |

## Backward Compatibility

- The new `graph` verb is additive. No existing verb, rule, or output format
  changes.
- `validate` output and exit codes are unchanged; `graph` is a separate
  projection over the same data.

## Open Questions

> [!IMPORTANT]
> **DEC-GR-001 (RESOLVED):** Should the graph include criteria from specs at
> `Status: DRAFT`, or only accepted ones? **Decision: include drafts.** The
> graph is a pure projection of what `validate` computes (R-GR-1), and
> `validate` does not filter by status. Excluding drafts would hide exactly the
> unverified links and broken edges a reviewer has not yet signed off on — the
> drift the graph exists to surface. No longer blocking.
