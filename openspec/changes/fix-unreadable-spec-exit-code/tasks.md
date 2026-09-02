# Milestones

## Milestone 1 — Translate the read failure into a typed error

- `openspec_graph/parse.py`: add `SpecReadError(Exception)` carrying `path`
  and `reason` (DEC-RE-002, DEC-RE-003); wrap `parse_spec`'s
  `path.read_text(...)` in `try/except OSError`, emit a `logger.debug` naming
  the path and the OS error, then `raise SpecReadError(path, exc.strerror or
  str(exc)) from exc` (DEC-RE-005). Add the module logger
  (`logging.getLogger("planlint.parse")`, no handler attached — `detect.py`'s
  convention) and add `"SpecReadError"` to `__all__`.
- `openspec_graph/__init__.py`: re-export `SpecReadError` from `.parse`,
  beside `NoOpenSpecTreeError`, and add it to `__all__` (R-RE-9).
- `tests/test_spec_read_errors.py`: unit tests for the translation — a
  directory named `spec.md` raises `SpecReadError` with `path` set, `reason`
  non-empty, and `__cause__` the original `OSError`, and a readable spec
  still parses (AC-RE-3). The debug records (AC-RE-10) stay a code-review
  check: this suite has no `caplog` harness, and adding one for two lines is
  more machinery than the claim is worth.
- `tests/test_decomposition.py`: extend `test_public_import_compatibility`
  with `SpecReadError` so the new public symbol is pinned like the rest.
- **Gate:** `make test` green.

## Milestone 2 — Exit 2, once, from every verb that reads specs

- `openspec_graph/cli.py`: import `SpecReadError`; add `_UNREADABLE_SPEC =
  "ERROR cannot read spec {path}: {reason}"` beside `_NOT_A_DIRECTORY`, with
  a comment recording why it is single-sourced (R-RE-6); add
  `_report_unreadable(exc, root)` — one `logger.debug` abort record, one
  stderr line rendered through `detect.to_posix_relative`, `return 2`
  (DEC-RE-006).
- `openspec_graph/cli.py`: wrap `cmd_validate`'s parse/evaluate loop and
  `cmd_waivers`' parse comprehension in `except SpecReadError` returning
  through the helper; add a third `except SpecReadError` clause to
  `cmd_graph`'s existing `build_graph` try block, after the
  `NoOpenSpecTreeError` clause, with a comment stating why the catch lives in
  the CLI and not in `graph.py` (R-RE-5).
- `openspec_graph/graph.py`: document in `build_graph`'s docstring that it
  propagates `SpecReadError` — no code change, no new import, and no `cli`
  import (R-RE-5, R-RE-9).
- `tests/test_spec_read_errors.py`: a `PARSING_VERBS` parametrization over
  `validate`, `validate --json`, `waivers`, `waivers --format json`,
  `graph --format json`, `graph --format mermaid` driving both the exit-2 and
  the no-traceback assertions (AC-RE-1); message content and the empty-stdout
  check (AC-RE-2); the fail-closed test that a readable passing spec beside
  an unreadable one does not produce `PASS` (AC-RE-5); the non-success pair
  proving a rule violation still exits 1 and a clean tree still exits 0
  (AC-RE-4); and a readable tree still rendering a valid graph, so the
  `except` clause cannot have swallowed the success path (AC-RE-6).
- **Gate:** `make test` green.

## Milestone 3 — Say plainly that `--change` is OpenSpec-only

- `openspec_graph/cli.py`: add `_NO_SPECS_FOR_CHANGE` and
  `_CHANGE_IS_OPENSPEC_ONLY` constants and one shared
  `_report_no_specs_for_change(prof, change)` helper that selects the second
  only when `prof.speckit_root and not prof.openspec_root`, formats through
  the chosen template, and returns 2. Both `cmd_validate`'s and `cmd_graph`'s
  `--change` guards return through it, so neither the wording, the selection
  rule, nor the exit code is duplicated (R-RE-6, R-RE-7, DEC-RE-006,
  DEC-RE-007).
- `tests/test_spec_read_errors.py`: the SpecKit-only `--change` message names
  the limitation and exits 2 (AC-RE-7), and the OpenSpec target keeps the
  original line with no mention of SpecKit (AC-RE-8). The existing
  `tests/test_skill_contract.py::test_unknown_change_package_exits_two` /
  `::test_graph_unknown_change_exits_two` equality assertions must keep
  passing untouched.
- **Gate:** `make test` green.

## Milestone 4 — Document the new exit-2 case and close the drift guards

- `skills/planlint-spec-governance/references/exit-codes.md`: new "Exit 2, by
  verb" entry for an unreadable spec, quoting `ERROR cannot read spec
  <path>: <reason>` verbatim, and a sentence for the SpecKit `--change`
  case; keep the existing entries and the "exit 1 means findings, and only
  findings" framing intact (R-RE-10).
- Confirm by review that `_UNREADABLE_SPEC`, `_NO_SPECS_FOR_CHANGE` and
  `_CHANGE_IS_OPENSPEC_ONLY` each appear exactly once under
  `openspec_graph/` and each reaches stderr through exactly one helper — no
  automated single-sourcing check was added, so this stays a review step
  (AC-RE-9). `tests/test_skill_contract.py::test_exit_two_messages_match_the_documented_contract`
  keeps covering the no-tree wording it already pinned.
- `CHANGELOG.md`: one entry describing the exit-code correction and the
  `--change` wording, in the style of the existing `DEC-SD-001` entry.
- Confirm `detect.py` is untouched and its two skip-and-continue tests still
  pass unmodified (AC-RE-11).
- Dogfood: run `planlint validate` against this repo with this change package
  present.
- **Gate:** `make pre-pr` green; `planlint validate` clean.

## Milestone 5 — Record the `--change` asymmetry found after implementation

- Reproduce and record the measured pair (`DEC-RE-009`): with a readable
  `changes/good` and an unreadable `changes/broken/specs/cap/spec.md`,
  `validate --change good` exits 0 `PASS` and
  `graph --change good --format json` exits 2. Narrow `C-RE-2` to unscoped
  runs and add `AC-RE-12` citing the manual reproduction rather than a test
  that does not exist.
- Leave the regression test to whichever change next touches `--change`
  scoping: writing one here would mean pinning a behaviour (`validate
  --change` staying silent about out-of-scope specs) that follows from
  `DEC-WL-003`/`DEC-AD-004` rather than from this change.
- **Gate:** `make validate` clean with the amended spec present.
