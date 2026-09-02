# Milestones

## Milestone 0 — Design + peer review

Done before drafting: the roadmap's `delta --since <ref>` sketch was taken
apart and rejected on three independent grounds, recorded as `DEC-DL-001`
rather than left as an unexplained divergence from `docs/differentiation-roadmap.md`.
The `--baseline CARD.json` form, the attribution boundary against G004/G005
(`DEC-DL-002`), and the not-a-`Finding` separation (`DEC-DL-003`) all come out
of that pass. Nothing below has been implemented.

- Hand this package to `spec-adversary` before writing any code against it.
- **Gate:** review complete; `Status:` in `specs/delta-lint/spec.md` raised
  from `DRAFT` by a human, not by the implementer.

## Milestone 1 — `delta.py`, the pure module

- `openspec_graph/delta.py` (new): `DELTA_SCHEMA_VERSION = 1`; frozen
  `DeltaEntry` dataclass with fields `path`, `change`, `kind`, `subject`,
  `was`, `now`, `detail` and an `as_dict()` emitting them in that fixed order
  (mirrors `ledger.LedgerEntry.as_dict()`);
  `build_delta(baseline: Mapping[str, object], profile: detect.StackProfile,
  specs: Sequence[ParsedSpec], root: Path | None = None) -> list[DeltaEntry]`.
  Module docstring records the purity posture (`R-DL-10`) and why no git call
  exists (`DEC-DL-001`), the way `ledger.py`'s and `machinery.py`'s do.
- The four entry kinds per `R-DL-4`, each gated on the baseline having
  satisfied the citation (`R-DL-2`) and on the baseline card actually carrying
  the field (`R-DL-6` — skip an absent key, never read it as an empty set).
- `threshold` entries computed through `parse_semantics.threshold_values` with
  G001's single-unambiguous-match condition (`R-DL-5`, `DEC-DL-004`); no second
  implementation of "does this line cite the floor".
- Sort on `(path, kind, subject)` inside `build_delta`, never in a renderer
  (`DEC-DL-010`). Paths through `detect.to_posix_relative`, and `change` via
  `ledger.owning_change` — reused, not re-derived.
- `tests/test_decomposition.py`: `_NEW_MODULES` gains `"delta"`, putting the
  module under the existing stdlib-only, no-`subprocess`, and import-boundary
  guards (`AC-DL-13`).
- **Gate:** `make test` — `test_new_modules_stdlib_only`,
  `test_only_detect_imports_subprocess`, `test_import_boundary_discipline`
  pass with the new module registered.

## Milestone 2 — `tests/test_delta.py` (none of these tests exist yet)

This is the gating work for the whole package, not a follow-up.
`tests/test_spec_test_citations.py` statically resolves every `_Verified by:_`
selector in `openspec/changes/*/specs/*/spec.md` against the test names it
parses out of `tests/`, and fails the suite for any it cannot find. Every
selector this package's spec cites and marks `(test not yet written)` is
currently unresolvable, so **the suite is red until these are written** and the
package is not done before it is green.

- New `tests/test_delta.py`, pure unit tests over `build_delta`, with a module
  docstring stating the attribution boundary the verb exists to draw:
  - `test_delta_reports_a_spec_citing_the_old_coverage_floor` (AC-DL-1)
  - `test_delta_names_the_removed_make_target` (AC-DL-2)
  - `test_delta_names_the_removed_invariant`,
    `test_delta_names_the_removed_adr` (AC-DL-3)
  - `test_every_delta_entry_corresponds_to_a_machinery_change` — over a
    fixture carrying all four kinds at once (AC-DL-4)
  - `test_delta_on_an_identical_baseline_is_empty` — asserts the fixture has
    real citations first, so it cannot pass vacuously (AC-DL-5)
  - `test_delta_ignores_a_citation_already_broken_in_the_baseline` — asserts
    both halves: empty delta list *and* the G004 finding present in the same
    fixture (AC-DL-6)
  - `test_delta_entries_are_stable_ordered` — fixture specs created in an
    order that differs from the sorted one (AC-DL-7)
  - `test_delta_skips_a_field_absent_from_an_older_baseline_card` (AC-DL-8)
  - `test_delta_ignores_an_ambiguous_threshold_line` (AC-DL-9)
  - `test_delta_entry_as_dict_shape` — the field set and order pinned, the way
    `test_ledger_entry_as_dict_shape` pins `LedgerEntry`'s
  - `test_delta_entries_never_reach_the_finding_stream` (AC-DL-11)
- **Gate:** `make test` green, including
  `tests/test_spec_test_citations.py::test_every_spec_test_citation_resolves_to_a_real_test`;
  100% line/branch coverage on `openspec_graph/delta.py`, matching the bar
  `mermaid.py` and `ledger.py` shipped at.

## Milestone 3 — `cmd_delta` and the CLI surface

- `openspec_graph/cli.py`: `cmd_delta` — build the profile, reject a missing
  spec tree with the shared exit-2 wording, read and validate the baseline
  (message shape copied from `cmd_detect`'s `--diff` branch, `R-DL-9`), gather
  and parse specs through `_gather_spec_files`/`parse_spec` with the existing
  `SpecReadError` → `_report_unreadable` handling, call
  `dialect_card.diff_cards` and `delta.build_delta`, render, and return
  0/1/2 per `R-DL-8`.
- `openspec_graph/cli.py`: `p_delta` subparser — `--baseline PREV_CARD_JSON`
  (required), `--format {text,json}` defaulting to `text`, `--dialect`. No
  `--fail-on`, no `--since`, no `--change` (`DEC-DL-009`, and the proposal's
  Non-Goals).
- Text rendering: the machinery changes first as context, then one `STALE:`
  line per entry naming the spec and what went stale; `PASS: no spec citation
  went stale since the baseline` and exit 0 when the list is empty — the
  `FAIL:`/`PASS:` idiom `cmd_detect --diff` already uses.
- `tests/test_cli_surface.py`: `ALLOWED_VERBS` gains `"delta"` (`AC-DL-14`) —
  `test_cli_verbs_are_exactly_the_allow_list` fails until it does.
- CLI-level tests in `tests/test_graft.py`, beside the existing
  `detect --diff` and `waivers` ones — none exist yet:
  `test_cli_delta_json_lists_stale_citations_with_schema_version`,
  `test_cli_delta_exits_zero_on_an_identical_baseline`,
  `test_cli_delta_exits_one_when_a_citation_went_stale`,
  `test_cli_delta_with_missing_baseline_is_a_usage_error`,
  `test_cli_delta_with_a_non_object_baseline_is_a_usage_error`,
  `test_cli_delta_json_is_byte_identical_across_runs`,
  `test_cli_delta_never_writes_to_the_target_repo` (reusing the recursive
  snapshot helper `test_detect_never_writes_to_the_target_repo` uses),
  `test_cli_delta_text_output_names_old_and_new_threshold`.
- Confirm nothing rule-shaped changed: `openspec_graph/rules.py`'s `RULES`
  tuple and `README.md`'s rules table untouched, and
  `_EXPECTED_HASHES["validate"]`/`["graph"]`/`["rules"]` not re-pinned
  (`C-DL-1`, `C-DL-4`, `AC-DL-11`). If any hash moves, stop — `delta` has
  leaked into a stream it must not be in.
- **Gate:** `make ci` green — AC-DL-1..14.

## Milestone 4 — Docs, and the reference that would otherwise go stale

- `README.md`: `delta` in the CLI verb list, plus the worked two-step example
  (`planlint --target . detect --format json > base.json`, then, after the
  machinery moves, `planlint --target . delta --baseline base.json`), and the
  worktree recipe for "since a ref" so the rejected `--since` has a documented
  replacement rather than an absence.
- `skills/planlint-spec-governance/references/exit-codes.md`: `delta` added to
  the exit-2 list, and "The one exit-1 case that is not a finding" becomes two
  cases (`DEC-DL-008`). Left unedited, this reference would describe the CLI
  incorrectly the moment `delta` ships — the exact drift this tool fails other
  repositories for.
- `docs/differentiation-roadmap.md`: CP-5's section records that
  `--since <ref>` was rejected, the three reasons, and what shipped instead.
  Its `AC-DL-1`/`AC-DL-2`/`AC-DL-3` bullets are superseded by this package's
  own numbering and must say so, or two documents will claim the same ids for
  different criteria.
- `CHANGELOG.md`: one entry under the unreleased heading, in the style of the
  neighbouring `add-mermaid-graph-export` entry.
- Mark every AC in this package's own `specs/delta-lint/spec.md` `[x]` only as
  each is actually verified, and dogfood:
  `planlint --target . detect --format json > /tmp/base.json` then
  `planlint --target . delta --baseline /tmp/base.json` against this
  repository (expected: exit 0, empty list).
- **Gate:** `make pre-pr` green; `make docs-check` green (AC-DL-15).
