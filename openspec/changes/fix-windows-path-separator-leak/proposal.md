# Change: Fix Windows Path Separator Leak

## Why

Twelve sites across six modules (`graph.py`, `ledger.py`, `rule_types.py`,
`detect.py`, `scaffold.py`, `cli.py`) computed a "repo-relative path" for
display or persisted JSON via `str(path.relative_to(root))` — or by
f-string-interpolating a `Path` object directly — instead of
`path.relative_to(root).as_posix()`. `str(pathlib.Path)` renders with the
platform-native separator: identical to `.as_posix()` on POSIX, but
backslash-separated on Windows.

**Evidence:** eight tests already in this suite hardcoded a forward-slash
relative path and failed immediately on Windows, because the value under
test is exactly what these sites compute —
`tests/test_ledger.py::test_build_ledger_falls_back_to_the_full_path_when_not_under_root`
is representative: it asserts `entries[0].path ==
"/elsewhere/openspec/changes/c1/specs/cap1/spec.md"`, which only holds
when the separator is forward-slash. A ninth test,
`tests/test_decomposition.py::test_output_byte_identical`, failed as a
downstream symptom (its `_run_cli()` helper stripped the absolute
temp-dir prefix but never normalized separators inside a relative one).
`.github/workflows/ci.yml` pins every job to `runs-on: ubuntu-latest`, so
none of this had ever run on the one OS that would fail it.

The most severe instance passed its own nearby test for the wrong
reason: `tests/test_graft.py::test_init_pins_detected_conventions`
asserts `config["invariant_source"] == "CONTRACT.md"` against
`scaffold.py`'s `plan_init()` — but `"CONTRACT.md"` is a single path
segment, with no separator character in either OS's rendering, so it
cannot catch the bug regardless of platform. The bug only manifests once
the detected source is nested (e.g. `docs/CONTRACT.md`, a real candidate
`detect.py` already checks for), at which point `plan_init()` bakes a
backslash-separated path into both `openspec/specgraph.json` and
`openspec/project.md` — persisted repo state a user might commit, not a
transient print.

## What Changes

- New `to_posix_relative(path, root)` function in `openspec_graph/detect.py`
  — a pure, dependency-free helper. Returns
  `path.relative_to(root).as_posix()` when `path` is under `root`; falls
  back to `path.as_posix()` (never `str(path)`, and never raises) when it
  isn't, or when `root` is `None`.
- `graph.py`, `ledger.py`: their private relativizing helpers
  (`_relative_to`, `_relative`) become thin wrappers around it (`_relative`
  is deleted outright — `build_ledger()` calls the shared function
  directly).
- `rule_types.py`: `Finding.render()` uses it.
- `detect.py` itself: `StackProfile.adr_source_name`, `as_dict()`'s
  `invariant_source`/`adr_source` fields, and `_threshold()`'s three
  candidate branches all use it.
- `scaffold.py`: `plan_init()`'s `config["invariant_source"]` uses it —
  the field persisted into `specgraph.json`/`project.md`.
- `cli.py`: `init`/`new`'s per-file plan listing and `witness`'s
  confirmation message use it. `graph.py`'s `NoOpenSpecTreeError` message
  is fixed separately (proper `Path` joining instead of string
  concatenation onto a native `str(profile.root)`), since it embeds an
  absolute path, not a relative one. `cmd_validate`'s plain-text findings
  sort key also switches from `str(f.path)` to the shared function, so two
  findings at different paths sort in the same relative order on every
  host OS — an earlier draft of this change judged the sort key safe to
  leave untouched, reasoning `Finding.path` is always absolute so
  cross-machine comparison was never meaningful anyway; that reasoning
  conflated "identical string across machines" (true, irrelevant) with
  "same relative order within one machine's own run" (false — verified
  directly: `\` sorts after digits/uppercase letters while `/` sorts
  before them, so two sibling change directories can render in opposite
  order between Windows and POSIX for the identical repo).
- `tests/test_decomposition.py`: `_run_cli()`'s `<ROOT>` substitution also
  handles the JSON-escaped form of the root path (`\` becomes `\\` inside
  a JSON string), needed for `test_output_byte_identical` to actually
  pass on Windows now that the underlying content is correct.

## Non-Goals

- No change to any absolute, self-referential path: `StackProfile.root`,
  `StackProfile.openspec_root`, `validate --json`'s top-level `target`
  field, and `Finding.as_dict()`'s `path` field all stay platform-native.
  None of these is ever compared across machines or has a normally-relative
  case to be consistent with — posix-normalizing an absolute path buys no
  portability, only an unfamiliar-looking path for a Windows user reading
  their own filesystem's own convention back at them.
- No fix for the two other, unrelated Windows test-infra gaps identified
  in the same investigation (symlink-fixture privilege; an unguarded
  `["make", ...]` subprocess call in one test) — those are plain test
  edits with no product-code change, tracked separately without a change
  package of their own.

## Affected Capabilities

- `windows-path-separators`
