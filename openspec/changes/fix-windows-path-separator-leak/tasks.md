# Milestones

## Milestone 1 — Add the shared posix-relative-path function [DONE]

- `openspec_graph/detect.py`: `to_posix_relative(path, root)` — pure,
  module-level function (DEC-PS-003). `path.relative_to(root).as_posix()`
  on success; `path.as_posix()` on `ValueError` or when `root is None`
  (DEC-PS-001); never raises.
- `tests/test_graft.py`: 3 new direct unit tests for the function
  (root-relative, outside-root fallback, `root=None`) — full branch
  coverage of the new logic.
- **Gate:** `make test` green.

## Milestone 2 — Migrate every call site onto the shared function [DONE]

- `openspec_graph/graph.py`: `_relative_to()` becomes a thin wrapper
  delegating to `detect.to_posix_relative()` (kept importable —
  `tests/test_enterprise.py` imports it by name); `build_graph()`'s
  `invariant_source`/`adr_source` dict fields; `NoOpenSpecTreeError`'s
  message fixed separately via proper `Path` joining (R-PS-4), not the
  shared function, since it embeds an absolute path.
- `openspec_graph/ledger.py`: private `_relative()` helper deleted;
  `build_ledger()` calls `detect.to_posix_relative()` directly.
- `openspec_graph/rule_types.py`: `Finding.render()` calls it (drops its
  `contextlib.suppress` block entirely, and the now-unused `contextlib`
  import); `Finding.as_dict()` deliberately untouched (DEC-PS-002).
- `openspec_graph/detect.py`: `StackProfile.adr_source_name`'s `try`
  branch; `as_dict()`'s `invariant_source`/`adr_source` fields;
  `_threshold()`'s governance-policy/`.coveragerc`/`setup.cfg` candidates;
  `root`/`openspec_root` deliberately untouched (DEC-PS-002).
- `openspec_graph/scaffold.py`: `plan_init()`'s
  `config["invariant_source"]` — the field persisted into both
  `openspec/specgraph.json` and `openspec/project.md`.
- `openspec_graph/cli.py`: `cmd_init`/`cmd_new`'s per-file plan listing,
  `cmd_witness`'s confirmation message; `cmd_detect`'s and `cmd_validate
  --json`'s absolute-root fields deliberately untouched (DEC-PS-002).
  `cmd_validate`'s plain-text findings sort key ALSO migrated onto
  `to_posix_relative` (R-PS-5) — reversed from an initial "leave it
  untouched" decision after independent adversarial review found the
  original reasoning wrong (DEC-PS-004).
- `tests/test_ledger.py`, `tests/test_enterprise.py`, `tests/test_graft.py`:
  existing forward-slash assertions (previously failing only on Windows)
  now pass on every OS; `test_graph_relative_to_outside_root_falls_back`'s
  outside-root assertion updated per DEC-PS-001;
  `test_finding_as_dict_path_field_stays_absolute_and_native` added as a
  real regression guard for DEC-PS-002's "deliberately unchanged" claim.
- `tests/test_graft.py`: `test_detect_governance_policy_locator_uses_forward_slashes_for_a_nested_path`,
  `test_as_dict_reports_a_multi_segment_invariant_source_with_forward_slashes`,
  and `test_plan_init_persists_a_forward_slash_invariant_source_to_disk`
  added — the last one is the sibling of `test_init_pins_detected_conventions`
  with a *nested* fixture, since the existing test's single-segment
  fixture cannot exercise the bug on either OS.
- `tests/test_graft.py`: `test_cli_init_dry_run_prints_forward_slash_paths`,
  `test_cli_new_dry_run_prints_forward_slash_paths`,
  `test_cli_witness_prints_a_forward_slash_path` added.
- `tests/test_graph.py`: `test_no_openspec_tree_error_has_no_mixed_separators`
  added — the two pre-existing missing-tree tests only substring-check
  `"openspec/"`, which was already true in the buggy message's fixed
  prefix regardless of how the root was joined, so neither could actually
  catch this one.
- `tests/test_graft.py`: `test_cli_validate_text_finding_order_is_consistent_across_host_os`
  added (R-PS-5) — two sibling change directories whose native-vs-posix
  sort order provably diverges (`add-thing`/`add-thing2`); replaces an
  earlier, incorrect citation of `test_findings_order_is_stable_across_specs`,
  which only exercises `validate --json` (never sorted) and never actually
  ran the plain-text sort key at all.
- `docs/hooks.md`: corrected a now-stale claim in "Adding a new pure
  derived-output module" ("none of the three imports another sibling
  module") — `ledger.py` now imports `detect.to_posix_relative`.
- `tests/test_graft.py`, `tests/test_graph.py`: both had their own inline
  `write_spec()` redeclaration (missing `encoding="utf-8"`, unlike
  `tests/support.py`'s) instead of importing the shared one — found by an
  independent scan while investigating this change, fixed by importing
  `tests.support.write_spec` in both. `tests/test_decomposition.py::test_helpers_not_duplicated_inline`
  strengthened to scan every `test_*.py` file for either name
  (`write_spec`/`_write_spec`) instead of a fixed two-file list with only
  the underscore-prefixed name, so this class of drift is caught
  automatically going forward.
- **Gate:** `make test` green.

## Milestone 3 — Fix the test infrastructure blind spot, confirm byte-identical output [DONE]

- `tests/test_decomposition.py`: `_run_cli()`'s `<ROOT>` substitution
  extended to also strip the JSON-escaped form of the root path
  (DEC-PS-005) — `validate --json`'s native-separator `target` field
  (deliberately unchanged, DEC-PS-002) gets backslash-doubled by
  `json.dumps` on Windows, which the original single-pass replace never
  matched.
- `test_output_byte_identical` confirmed to reproduce the exact
  pre-existing Linux-pinned hashes for `validate`/`graph`/`rules` once
  both this milestone and Milestone 2 are applied — not merely different
  output, byte-identical to what Ubuntu CI has always produced.
- `planlint validate` run against this repo itself (dogfood check) after
  adding this change package: clean.
- **Gate:** `make pre-pr` green; `planlint validate` clean.
