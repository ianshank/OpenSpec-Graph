# Spec: Windows Path Separators

> **Change:** `fix-windows-path-separator-leak`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

Twelve sites across six modules render a "repo-relative path" for display
or persisted JSON via `str(path.relative_to(root))`, or by
f-string-interpolating a `Path` object directly, instead of
`path.relative_to(root).as_posix()`. `str(pathlib.Path)` uses the
platform-native separator: identical to `.as_posix()` on POSIX, but
backslash-separated on Windows.

**Evidence:** eight tests already in this suite hardcoded a forward-slash
relative path and failed immediately on Windows, because the value under
test is exactly what these sites compute —
`test_build_ledger_falls_back_to_the_full_path_when_not_under_root` is
representative: it asserts `entries[0].path ==
"/elsewhere/openspec/changes/c1/specs/cap1/spec.md"`, which only holds
when the separator is forward-slash. `.github/workflows/ci.yml` pins
every job to `runs-on: ubuntu-latest`, so this has never run on the OS
that would fail it.

The most severe instance passed its own nearby test today for the wrong
reason: `test_init_pins_detected_conventions` asserts
`config["invariant_source"] == "CONTRACT.md"` against `scaffold.py`'s
`plan_init()` — but `"CONTRACT.md"` is a single path segment, with no
separator character in either OS's rendering, so this test cannot catch
the bug regardless of platform. The bug only manifests once the detected
source is nested (e.g. `docs/CONTRACT.md`, a real candidate `detect.py`
already checks for), at which point `plan_init()` bakes a
backslash-separated path into both `openspec/specgraph.json` and
`openspec/project.md` — permanently committed repo state, not a
transient print.

---

## Requirements

- R-PS-1: Every relative-path string this package emits — `validate`'s
  text and `--json` output, `graph --format json`/`mermaid`, `waivers`'
  text and `--json` output, the G008/G009 rule messages, `init`/`new`'s
  per-file plan listing, `witness`'s confirmation message, and the
  `invariant_source` snapshot `init` persists into
  `openspec/specgraph.json` and `openspec/project.md` — MUST use forward
  slashes, regardless of the host OS.
- R-PS-2: A single shared function (`detect.to_posix_relative`) MUST
  compute every such string; no module MUST independently call
  `path.relative_to(root)` and stringify the result on its own.
- R-PS-3: When `path` is not located under `root`, the shared function
  MUST fall back to `path.as_posix()`, never to the platform-native
  `str(path)`, and MUST NOT raise.
- R-PS-4: An error message that embeds an absolute path (e.g.
  `graph`'s "no openspec/ directory found at ...") MUST render that path
  in one consistent form, never a mix of native separators and a literal
  forward slash concatenated onto it.
- R-PS-5: `validate`'s plain-text finding order MUST be identical across
  host OSes for an identical set of findings — the sort key MUST use the
  same posix-normalized path the rendered line displays
  (`detect.to_posix_relative`), never `str(f.path)`.
- C-PS-1: Absolute, self-referential paths — `StackProfile.root`,
  `StackProfile.openspec_root`, `validate --json`'s top-level `target`
  field, and `Finding.as_dict()`'s `path` field — MUST NOT be changed by
  this fix; none of them is ever compared across machines, so the host
  OS's native separator remains the correct rendering.
- C-PS-2: `Finding.path`'s `None` case (a whole-tree finding with no
  declaring path unset) MUST keep sorting exactly as `str(None) ==
  "None"` did before this fix — the sort key MUST NOT call
  `to_posix_relative` on a `None` path, since that function requires a
  real `Path`. In practice this branch is never exercised today (G006/G009
  always set a real path instead, `DEC-WL-004`), but the fallback stays
  explicit rather than relying on that guarantee silently.

---

## Decisions

- **DEC-PS-001:** the shared function's outside-root fallback returns
  `path.as_posix()`, not `str(path)` — even though `graph._relative_to`'s
  pre-existing test asserted the fallback equals `str(outside)`. That
  assertion was tautological: it compared the function's own output to
  `str()` computed at test-run time, so it trivially matched whatever the
  implementation already returned, on any OS — it never actually pinned a
  specific separator. `ledger.build_ledger`'s sibling fallback test
  (`test_build_ledger_falls_back_to_the_full_path_when_not_under_root`)
  already hardcoded a forward-slash absolute-path literal for the
  identical scenario. A single shared function can only satisfy both
  consistently by always normalizing to posix, so
  `test_graph_relative_to_outside_root_falls_back`'s first assertion was
  updated, in the course of migrating `graph._relative_to` onto the
  shared function, to compare against `outside.as_posix()`.
- **DEC-PS-002:** absolute, self-referential fields —
  `StackProfile.root`/`openspec_root`, `validate --json`'s top-level
  `target` field, and `Finding.as_dict()`'s `path` field — are excluded
  from this fix (C-PS-1). None of them is ever compared across two
  checkouts of the same repo: two developers' or two CI runners' absolute
  paths to "this repo" never match to begin with, so posix-normalizing
  them buys no portability, only an unfamiliar-looking path for a Windows
  user reading their own filesystem's own convention back at them.
  `Finding.as_dict()` specifically stays untouched despite
  `Finding.render()` (the human-readable counterpart, built from the same
  `Finding.path` field) being fixed — this is not an inconsistency to
  "correct" later: `render()`'s `path` field is *normally* relative to
  `root`, so its rare outside-root fallback stays consistent *within that
  field* by also being posix; `as_dict()`'s `path` field is *always*
  absolute (traced through every `Finding(...)` construction site back to
  a resolved `openspec_root`), so there is no normally-relative case for
  its separator to be consistent with. Fixing `as_dict()` "for
  consistency" would in fact introduce the inconsistency, not remove one.
- **DEC-PS-003:** the shared function lives directly in `detect.py`, not
  in a new module. An earlier draft of this change proposed a new
  `openspec_graph/paths.py`, reasoning that `ledger.py`/`rule_types.py`
  couldn't safely depend on `detect.py` without cycle risk — that premise
  was checked against the real import graph and found false:
  `rule_types.py` already does `from .detect import StackProfile`, and
  `graph.py`/`scaffold.py`/`cli.py` all already import `detect.py` too —
  four of the five consumers already have a direct, existing import edge
  to it. Only `ledger.py` needs a new one, and `detect.py`'s own imports
  (`dialect_card`, `machinery`, `witness`) provably never import
  `ledger.py`, so that edge is cycle-safe. Placing the function in
  `detect.py` means `graph.py`/`cli.py` need zero new import lines at all
  (they already `from . import detect`); this is strictly less invasive
  than a new module and does not rest on a false premise.
- **DEC-PS-004 (reversed after independent adversarial review):**
  `cli.py`'s plain-text findings sort key changes from
  `sorted(findings, key=lambda f: (str(f.path), f.rule))` to a
  `to_posix_relative`-based key (R-PS-5). A first version of this change
  left it unchanged, reasoning `Finding.path` is always absolute, so
  "two different machines produce entirely different absolute prefixes
  regardless of separator style, making OS-independent ordering
  incoherent as a goal." That argument answers a different question than
  the one that matters: not "does the exact string match across two
  different machines' checkouts" (irrelevant, correct as far as it goes),
  but "does the *relative order* of findings for the *same* repo stay
  identical regardless of which OS produced the run" (it did not).
  Verified directly by ordinal comparison: `\` (0x5C) sorts after every
  digit and uppercase letter, while `/` (0x2F) sorts before them — so two
  sibling change directories whose names differ only by a trailing digit
  (e.g. `add-thing` vs. `add-thing2`, this project's own real naming
  style — cf. `fix-u003-mandatory-given`/`fix-u004-body-blind-modal-check`)
  render in **opposite** relative order on Windows vs. POSIX for an
  identical set of findings. The original citation for "this doesn't
  matter, and it's tested" (an earlier draft of AC-PS-11, citing
  `test_findings_order_is_stable_across_specs`) was itself wrong: that
  test only exercises `validate --json`, whose `"findings"` array is raw
  insertion order and never sorted at all (`cli.py`'s `--json` branch);
  the sort key only runs on the plain-text branch, which no test
  exercised before this correction — a citation-without-execution-truth
  gap of exactly the kind `add-witness-mode`'s own spec warns against,
  just applied to an acceptance criterion instead of a `_Verified by:`
  line. AC-PS-11 now cites a real, dedicated test instead
  (`test_cli_validate_text_finding_order_is_consistent_across_host_os`).
- **DEC-PS-005:** `tests/test_decomposition.py::_run_cli()`'s `<ROOT>`
  substitution also strips the JSON-escaped form of the root path (each
  `\` doubled to `\\`), not only the raw form. `validate --json`'s
  `target` field is deliberately left absolute and native-separator
  (DEC-PS-002), and `json.dumps` escapes each backslash in that field —
  so on Windows the JSON text contains `C:\\Users\\...` (doubled
  backslashes as literal characters), which the original single-pass,
  raw-form-only replace never matched. Verified directly: adding the
  second pass makes `test_output_byte_identical`'s three hashes
  (`validate`, `graph`, `rules`) match the pre-existing Linux-pinned
  values exactly, confirming this fix's output is byte-identical to what
  Ubuntu CI has always produced, not merely "different and hopefully
  better."

---

## Acceptance Criteria

- [x] **AC-PS-1:** `graph --format json`'s `invariant_source`/
  `adr_source` fields, every rendered spec node's path, and
  `graph._relative_to`'s outside-root fallback, all use forward slashes
  on Windows. (R-PS-1, R-PS-2, R-PS-3, DEC-PS-001)
  _Verified by:_ `pytest -k "test_to_posix_relative_renders_a_path_under_root_with_forward_slashes or test_to_posix_relative_falls_back_to_the_full_path_when_not_under_root or test_graph_relative_to_outside_root_falls_back"` · stage: `make test`

- [x] **AC-PS-2:** `planlint waivers`' entries, in both text and
  `--json` form, report forward-slash paths — including a spec path
  that falls outside `--target`. (R-PS-1, R-PS-2, R-PS-3)
  _Verified by:_ `pytest -k "test_build_ledger_captures_rule_path_line_reason or test_build_ledger_orders_by_path_then_line_then_rule or test_build_ledger_relativizes_path_against_root or test_build_ledger_falls_back_to_the_full_path_when_not_under_root"` · stage: `make test`

- [x] **AC-PS-3:** `validate`'s findings, in plain-text form, report
  forward-slash paths — including a finding whose path lies outside
  `--target`. (R-PS-1, R-PS-2)
  _Verified by:_ `pytest -k test_finding_render_when_path_outside_root` · stage: `make test`

- [x] **AC-PS-4:** `detect.py`'s `adr_source_name` property, and the
  `G009` message that names it, use forward slashes. (R-PS-1)
  _Verified by:_ `pytest -k "test_adr_source_name_uses_the_real_directory_name_when_present or test_g009_fires_for_a_declared_adr_no_spec_cites"` · stage: `make test`

- [x] **AC-PS-5:** `planlint init` and `planlint new`'s per-file plan
  listing (the `create` / `skip (exists)` lines), and `planlint
  witness`'s confirmation message, show forward-slash paths. (R-PS-1)
  _Verified by:_ `pytest -k "test_cli_init_dry_run_prints_forward_slash_paths or test_cli_new_dry_run_prints_forward_slash_paths or test_cli_witness_prints_a_forward_slash_path"` · stage: `make test`

- [x] **AC-PS-6 (non-success):** `planlint init` never persists a
  backslash-separated `invariant_source` into `openspec/specgraph.json`
  or `openspec/project.md`, even when the detected source is nested two
  or more directories deep. (R-PS-1, R-PS-2)
  _Verified by:_ `pytest -k "test_plan_init_persists_a_forward_slash_invariant_source_to_disk or test_as_dict_reports_a_multi_segment_invariant_source_with_forward_slashes"` · stage: `make test`

- [x] **AC-PS-7:** `_threshold()`'s governance-policy locator uses
  forward slashes for a genuinely nested candidate path. (R-PS-1, R-PS-2)
  _Verified by:_ `pytest -k test_detect_governance_policy_locator_uses_forward_slashes_for_a_nested_path` · stage: `make test`

- [x] **AC-PS-8:** `graph`'s "no openspec/ directory found" error message
  renders the target path with one consistent separator, never a native
  path with a literal forward slash concatenated onto it. (R-PS-4)
  _Verified by:_ `pytest -k test_no_openspec_tree_error_has_no_mixed_separators` · stage: `make test`

- [x] **AC-PS-9 (non-success):** `detect --format json`'s `root` field,
  `validate --json`'s `target` field, and `Finding.as_dict()`'s `path`
  field all remain unchanged, platform-native absolute paths — this fix
  does not touch any of them. (C-PS-1, DEC-PS-002)
  _Verified by:_ `pytest -k test_finding_as_dict_path_field_stays_absolute_and_native` · stage: `make test`

- [x] **AC-PS-10 (non-success):** the CLI/graph/rules JSON
  byte-identical regression guard passes on Windows, matching the
  pre-existing Linux-pinned hashes exactly — confirming this fix's output
  is byte-identical to Ubuntu CI's, not merely different. (R-PS-1, DEC-PS-005)
  _Verified by:_ `pytest -k test_output_byte_identical` · stage: `make test`

- [x] **AC-PS-11:** `validate`'s plain-text finding order is identical
  across host OSes for an identical set of findings — including two
  sibling change directories whose native-vs-posix sort order would
  otherwise diverge. A `None` path (never exercised today, DEC-WL-004)
  still sorts as `"None"`, unchanged. (R-PS-5, C-PS-2, DEC-PS-004)
  _Verified by:_ `pytest -k test_cli_validate_text_finding_order_is_consistent_across_host_os` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-PS-1..11 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
