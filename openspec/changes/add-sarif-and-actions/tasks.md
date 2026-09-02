# Milestones

> **Every `_Verified by:` selector in this package's spec that is marked
> "(test not yet written)" names a test that does not exist yet.**
> `tests/test_spec_test_citations.py` statically resolves every citation
> across `openspec/changes/*/specs/*/spec.md` and fails the suite when one
> does not match a collected test name. So `make test` is red for this
> branch from the moment `spec.md` lands until the tests below are written —
> that is the intended pressure, not an accident, and writing them is the
> gating work of Milestones 2 through 6, not a follow-up. Nothing in this
> package may be marked done while a citation is unresolved.

## Milestone 0 — Design + grounding pass

- Ground `docs/differentiation-roadmap.md`'s `CP-6` sketch against the
  current tree rather than implementing the sketch. Two of its assumptions
  do not survive contact and are corrected in the spec:
  `Finding.line` is `0` for every finding the CLI can produce, so SARIF's
  `startLine >= 1` has no valid value to carry (`DEC-SA-003`); and
  `tests/test_adopter_urls.py::_adopter_files()` does not glob `.github/`,
  so a composite action's install line is not covered by the guard the
  sketch's touch map assumed (`DEC-SA-009`).
- Record every non-obvious call as `DEC-SA-001` through `DEC-SA-013`.
- **Gate:** `make validate`

## Milestone 1 — Change package

- Write `openspec/changes/add-sarif-and-actions/proposal.md`, this
  `tasks.md`, and `specs/sarif-output/spec.md`, spec-first, before any
  implementation. Every acceptance criterion starts unchecked.
- **Gate:** `make validate`

## Milestone 2 — `sarif.py` pure module

- New `openspec_graph/sarif.py`: `to_sarif(findings, rule_table, *,
  tool_version) -> dict`, pure, stdlib-only, zero intra-package import,
  taking already-serialized finding dicts (`Finding.as_dict(root)`'s output)
  rather than `Finding` objects or a `Path` (`DEC-SA-007`).
- Module-level `SEVERITY_LEVELS` mapping plus an explicit fail-upward default
  — an unknown severity becomes `"error"`, never `"none"` (`DEC-SA-008`).
- `tool.driver.rules` built from the passed rule table, full registry, in
  table order; `ruleIndex` computed from that same list so the two cannot
  disagree (`DEC-SA-005`, `DEC-SA-006`).
- Location construction: repository-relative `uri` with
  `uriBaseId: "%SRCROOT%"`; `region` emitted only for `line >= 1`; empty
  `locations` for a pathless finding (`DEC-SA-003`, `DEC-SA-004`).
- New `tests/test_sarif.py` with the pure unit tests the spec cites:
  `test_sarif_output_has_the_required_2_1_0_shape`,
  `test_error_severity_maps_to_sarif_error`,
  `test_severity_map_covers_every_severity`,
  `test_an_unknown_severity_maps_up_not_to_none`,
  `test_a_finding_with_no_path_is_emitted_without_a_location`,
  `test_no_finding_is_ever_dropped_from_the_sarif_log`,
  `test_a_line_of_zero_emits_no_region`,
  `test_a_real_line_emits_a_start_line`,
  `test_driver_rules_mirror_the_rule_table`,
  `test_every_result_rule_index_resolves_to_its_rule_id`.
- **Gate:** `make test`

## Milestone 3 — CLI wiring

- `openspec_graph/cli.py`: `validate` gains `--format {text,json,sarif}`
  defaulting to `text`; `--json` becomes an exact alias of `--format json`
  (`DEC-SA-001`); `--json` with `--format sarif` is rejected at the CLI edge
  with exit 2, a stderr message naming both flags, and no stdout output
  (`DEC-SA-002`); `--json` with `--format json` is accepted.
- The SARIF branch consumes the existing `ordered` list built by
  `sorted(findings, key=lambda f: _sort_key(f, prof.root))` and the existing
  `[f.as_dict(prof.root) for f in ordered]` projection — no second call to
  `rules.evaluate()` or `rules.evaluate_tree()` anywhere in the branch, and
  the exit-code line stays `1 if blocking else 0` (`DEC-SA-011`).
- `tool.driver.version` uses the memoized `cli._package_version()`; no second
  `importlib.metadata` lookup is introduced (`R-FE-8` still holds).
- End-to-end tests in `tests/test_sarif.py`:
  `test_sarif_and_json_report_the_same_finding_multiset`,
  `test_artifact_uri_is_repository_relative_posix`,
  `test_artifact_location_carries_the_srcroot_base_id`,
  `test_sarif_results_are_ordered_like_the_text_renderer`,
  `test_json_flag_is_an_exact_alias_of_format_json`,
  `test_json_with_format_sarif_is_a_usage_error`,
  `test_json_with_format_json_is_accepted`,
  `test_sarif_output_is_byte_stable_across_runs`.
- **Gate:** `make ci`

## Milestone 4 — Existing guards extended to the new surface

- `tests/test_skill_contract.py::READ_ONLY_INVOCATIONS` gains
  `("validate", "--format", "sarif")`, so the existing whole-tree digest test
  covers it. Confirm the invocation exits 0 or 1 against the populated
  fixture — the test's own guard fails a verb that exits 2, because an
  unchanged tree proves nothing if the command refused to run.
- `tests/test_decomposition.py::_NEW_MODULES` gains `"sarif"`, bringing the
  stdlib-only and import-boundary guards to bear on it.
- Confirm empirically — not by assumption — that
  `_EXPECTED_HASHES["validate"]`, `["graph"]`, and `["rules"]` are all
  unchanged, since no rule, no `Rule` field, and no `--json` payload key
  moved (`C-SA-1`, `C-SA-2`).
- Confirm `tests/test_cli_surface.py::ALLOWED_VERBS` is untouched: this
  change adds a format, not a verb (`C-SA-3`). While here, resolve the two
  selectors `AC-SA-16` flags as unconfirmed against the real test names in
  `tests/test_cli_surface.py` and `tests/test_rule_registry_docs.py`, and
  cite the real names rather than adding duplicate tests.
- **Gate:** `make ci`

## Milestone 5 — Composite action + adopter corpus

- New `.github/actions/planlint/action.yml`: composite action running Python
  setup, a pinned `planlint` install matching `templates/spec-gate.yml:34`'s
  existing range, `detect`, `validate --format sarif` redirected to a file,
  and `github/codeql-action/upload-sarif` with `if: always()` so a failing
  gate still annotates the pull request (`R-SA-16`).
- `tests/test_adopter_urls.py::_adopter_files()`: globs widened to
  `.github/actions/**/*.yml` and the root `.pre-commit-hooks.yaml`, so the
  new install line is discovered rather than exempt (`DEC-SA-009`). Confirm
  `test_the_corpus_actually_prints_install_commands_for_this_project`'s
  count assertion still holds after the corpus grows.
- New tests: `test_the_composite_action_declares_the_expected_steps`,
  `test_the_adopter_corpus_includes_the_composite_action`. Text-level, no
  YAML parser (`DEC-SA-013`, `C-SA-4`).
- **Gate:** `make ci`

## Milestone 6 — `.pre-commit-hooks.yaml`

- New root `.pre-commit-hooks.yaml` declaring an adopter-facing hook that
  invokes `planlint validate`. The existing contributor-facing
  `.pre-commit-config.yaml` is not modified (`DEC-SA-010`).
- New tests: `test_pre_commit_hooks_file_declares_a_validate_hook`,
  `test_the_two_pre_commit_files_do_not_collide`.
- **Gate:** `make ci`

## Milestone 7 — Docs, changelog, roadmap, close out

- `README.md`, `skills/planlint-spec-governance/SKILL.md` (structured-output
  paragraph and, if the format is documented per-flag there, the read-only
  table), and `CHANGELOG.md` describe `--format sarif`, the preserved
  `--json` alias, and the composite action.
- `docs/differentiation-roadmap.md`'s `CP-6` sketch replaced with an
  "implemented" writeup naming the two corrections this design made to it,
  mirroring how `CP-7` and `CP-GV` were closed out.
- Flip each acceptance criterion to `[x]` only as it is actually implemented
  and verified — never retroactively as already-true.
- Dogfood spot-check: `planlint --target . validate --format sarif` against
  this repository's own tree, piped to a file and confirmed to be valid JSON
  carrying one result per finding the same run's `--json` reports.
- **Gate:** `make pre-pr`
