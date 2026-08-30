# Tasks — Decompose God Files

- [x] Phase 1: shared test helpers — `tests/support.py` (duplicated `_write_spec`
      extracted, imported by test_enterprise + test_ci_hardening) + canonical
      fixtures in `tests/fixtures/`; tailored per-test fixture *variants* kept
      inline (they are not duplicates). Keep green.
- [x] Phase 2: split `scaffold.py` templates into `scaffold_templates.py`;
      keep `scaffold.py` as the write layer (WritePlan, plan_*, apply).
- [x] Phase 3: extract `graph.build_graph` into private helpers
      (`_add_spec_node`, `_add_requirement_nodes`, `_add_criterion_nodes`,
      `_add_invariant_edges`, `_add_finding_edges`, `_mark_orphan_requirements`,
      `_add_node`); output byte-identical.
- [x] Phase 4: split `parse.py` into `parse_semantics` (grammar + text helpers)
      / `parse_model` (dataclasses) / `parse_harness` / `parse_upstream`; keep
      `parse.py` as facade re-exporting the public surface (+ `_MAKE_REF`
      compat alias).
- [x] Phase 5: split `rules.py` into `rule_types` (Finding/Rule/severities) /
      `rules_generic` (G-rules) / `rules_harness` (H-rules) / `rules_upstream`
      (U-rules); keep `rules.py` as registry/facade (RULES, evaluate, rule_table).
- [x] Add guard tests (7, in `tests/test_decomposition.py`): public import
      compatibility, path-normalized byte-identical validate/graph/rules JSON,
      rules --json ordering stable, new-modules stdlib-only, shared helper not
      redeclared inline, import boundaries (catches relative imports), and
      detect/cli remain unsplit.
- [x] `make pre-pr` green; push; open PR; confirm CI green.
