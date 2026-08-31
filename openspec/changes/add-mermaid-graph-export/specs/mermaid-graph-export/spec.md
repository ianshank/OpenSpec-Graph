# Spec: Mermaid Graph Export

> **Change:** `add-mermaid-graph-export`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`graph --format json` computes the full dependency graph but nothing renders
it — a reviewer has to read raw JSON to see a change's structure. `--format
dot` is already, deliberately, rejected (`AC-GR-6`); `docs/next-steps.md` item
2 names a narrower path forward that doesn't reopen that rejection.

**Evidence:** `openspec_graph/cli.py::cmd_graph` only ever does
`json.dumps(graph, indent=2)`; no other consumer of `build_graph()`'s output
exists anywhere in this repo.

---

## Requirements

- R-GV-1: `graph --format mermaid` MUST render the graph as a Mermaid flowchart.
- R-GV-2: Real node ids (which contain slashes/dots) MUST be sanitized to
  synthetic identifiers; the real path/ident/text becomes the node's label.
- R-GV-3: Orphan and missing (`exists: False`) nodes MUST be styled distinctly
  from ordinary nodes.
- R-GV-4: Broken (`finding` or `exists: False`) edges MUST be styled distinctly.
- R-GV-5: `graph --change <name>` MUST scope which specs are rendered as
  nodes/edges, but MUST NOT scope what feeds the whole-tree orphan-invariant
  check — an invariant cited only outside the rendered scope MUST NOT be
  reported as falsely orphaned.
- R-GV-6: The whole-tree orphan-invariant check MUST still run, always
  unscoped, under `--change`, and its findings MUST still surface.
- C-GV-1: `--format dot`'s existing rejection (`AC-GR-6`) MUST be unrevised —
  identical message, identical exit code.
- C-GV-2: `mermaid.py` MUST be pure and stdlib-only, taking exactly
  `build_graph()`'s existing return dict — never changing its shape.

---

## Decisions

- **DEC-GV-001 (found by adversarial review before implementation):** the
  first design considered filtering `spec_files` before `build_graph()`'s
  existing per-spec loop, the same way `cmd_validate --change` filters before
  its own loop. But `build_graph()`'s loop also feeds
  `rules.evaluate_tree()` — scoping both would report every invariant cited
  outside the rendered scope as falsely orphaned, exactly the bug
  `DEC-WL-003` already exists to prevent in `cmd_validate`. Resolved:
  `build_graph()`'s new `spec_files` param scopes rendering only; the specs
  fed to `evaluate_tree()` are always the full, unscoped tree.
- **DEC-GV-002:** unlike `cmd_validate --change` (which skips the whole-tree
  orphan-invariant check entirely under `--change`, with an `INFO` note),
  `graph --change` keeps running it, unscoped, and includes its results. An
  orphan invariant is, by definition, cited by no living spec anywhere — so
  surfacing it isn't leaking a different change's content into a scoped
  picture; it's a fact about the invariant source itself.
- **DEC-GV-003:** `--format mermaid` does not revise `AC-GR-6`. That rejection
  is specifically about image-producing rendering, which requires an external
  engine (Graphviz) in every viewing context; Mermaid is text that GitHub/
  GitLab render natively, the same posture as the existing JSON output —
  `planlint` itself still performs no rendering.
- **DEC-GV-004:** the `--change` path filter, previously inline only in
  `cmd_validate` (`f"/changes/{change}/" in str(p)`), was extracted to
  `detect.filter_by_change()` and is now shared by both `cmd_validate` and
  `cmd_graph`, rather than letting a second copy exist to drift apart.

---

## Acceptance Criteria

- [x] **AC-GV-1:** `graph --format mermaid` on a clean spec emits a flowchart
  (starts with `flowchart LR`, contains a `-->|` edge). (R-GV-1)
  _Verified by:_ `pytest -k test_graph_format_mermaid_emits_a_flowchart` · stage: `make test`

- [x] **AC-GV-2:** A real, slash-containing node id never appears as a bare
  Mermaid identifier — every node is assigned a synthetic id. (R-GV-2)
  _Verified by:_ `pytest -k test_node_ids_are_sanitized_to_synthetic_identifiers` · stage: `make test`

- [x] **AC-GV-3:** Orphan nodes get the `orphan` class; missing (`exists:
  False`) nodes get the `missing` class; broken edges get a `linkStyle`. (R-GV-3, R-GV-4)
  _Verified by:_ `pytest -k "test_orphan_node_gets_the_orphan_class or test_missing_node_gets_the_missing_class or test_a_finding_edge_gets_a_broken_link_style or test_an_exists_false_edge_gets_a_broken_link_style"` · stage: `make test`

- [x] **AC-GV-4 (non-success):** `--format dot` is still rejected with the
  exact existing message and exit code after Mermaid ships. (C-GV-1)
  _Verified by:_ `pytest -k test_graph_dot_is_still_rejected_after_mermaid_ships` · stage: `make test`

- [x] **AC-GV-5:** `graph --change <name>` renders only that change's specs
  as spec nodes. (R-GV-5)
  _Verified by:_ `pytest -k test_graph_change_scopes_which_specs_are_rendered` · stage: `make test`

- [x] **AC-GV-6 (non-success):** an invariant cited only by a spec outside
  the `--change`-rendered scope is not falsely reported as orphaned. (R-GV-5, DEC-GV-001)
  _Verified by:_ `pytest -k test_graph_change_does_not_falsely_orphan_an_invariant_cited_outside_the_scope` · stage: `make test`

- [x] **AC-GV-7:** a genuinely orphaned invariant still surfaces as a node
  and finding under `--change` scoping. (R-GV-6, DEC-GV-002)
  _Verified by:_ `pytest -k test_graph_change_still_surfaces_a_genuinely_orphaned_invariant` · stage: `make test`

- [x] **AC-GV-8 (non-success):** `graph --change <unknown>` exits 2 naming
  the missing change; `graph --change` with no `openspec/` tree exits 2
  naming the missing directory. (R-GV-5)
  _Verified by:_ `pytest -k "test_graph_change_not_found or test_graph_change_with_no_openspec_dir"` · stage: `make test`

- [x] **AC-GV-9:** `tools/render_mermaid.py` renders a saved `graph --format
  json` file byte-identically to calling `mermaid.to_mermaid()` directly. (C-GV-2)
  _Verified by:_ `pytest -k test_render_mermaid_matches_to_mermaid_byte_for_byte` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-GV-1..9 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
