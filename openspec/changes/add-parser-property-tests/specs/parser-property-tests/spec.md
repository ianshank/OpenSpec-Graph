# Spec: Property-based tests over the parsers

> **Change:** `add-parser-property-tests`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

## Problem Statement

Four parsers read untrusted text — the Makefile reader, its `define`
stripper, the upstream spec parser and the negation matcher — and every one
of them was tested only on examples somebody had already imagined. The BOM
defect showed what that misses. A property states what the parser never does
on *any* input, and a generator supplies inputs no fixture author would.

## Requirements

- R-PB-1: `machinery.parse_makefile` MUST return identical facts for identical
  text, with `targets` sorted and free of duplicates, for arbitrary input.
- R-PB-2: `machinery.parse_makefile` MUST NOT raise on arbitrary text,
  including a leading BOM, NUL bytes, CRLF and the exotic line separators
  `str.splitlines()` honours.
- R-PB-3: `machinery.strip_define_blocks` MUST be idempotent: a second pass
  over its output changes nothing and reports no `define`.
- R-PB-4: `parse_upstream` MUST recognise exactly the requirement headings
  present at depths two to four, whatever filler headings, scenarios and
  prose surround them.
- R-PB-5: `Criterion.is_negative` MUST NOT change under printable-ASCII case
  changes of `text` or `note`, nor under surrounding whitespace.
- R-PB-6: The property suite MUST be deterministic per interpreter
  (`derandomize=True`) so a failure reproduces from its message alone.
- C-PB-1: `hypothesis` MUST be a `dev` extra only; `[project] dependencies`
  MUST stay empty.
- C-PB-2: No property MUST be marked `xfail` or have its strategy narrowed to
  exclude a found counterexample; the counterexample becomes a named test.

## Decisions

- **DEC-PB-001:** properties over invariants the code already claims, not
  over guessed behaviour. Each of the five restates a promise from a
  docstring or a design decision (`tuple(sorted(set(...)))`, "safe against an
  unfamiliar clone", the U005-versus-U002 split, `re.IGNORECASE` on every
  negation pattern), so a failure is a defect rather than an argument.
- **DEC-PB-002:** `derandomize=True`. This repository's own reasoning about
  gates is that a flaky one gets overridden and then removed; a fixed example
  stream makes every failure reproducible from its message. The cost is
  ongoing exploration, which is made an explicit local act.
- **DEC-PB-003:** determinism is per interpreter, and the docstring says so.
  `st.text()` samples from the running Python's Unicode tables, so 3.10 and
  3.13 draw different characters; each version is reproducible with itself,
  which is what a gate needs.
- **DEC-PB-004:** the casing property is stated over printable ASCII. U+0130
  lowercases to two code points and breaks `\bis\s+not`; that is Python's
  case mapping, not a matcher defect, and promising otherwise would be a
  property the code cannot keep.
- **DEC-PB-005:** mutation testing deferred, and the reason recorded rather
  than the tool half-adopted. A Make target for a mutation run that cannot
  execute without deselecting the repository's own guards would be a gate in
  name only.

## Acceptance Criteria

- [x] **AC-PB-1:** `parse_makefile` returns equal facts on two calls with the
  same generated text, and its targets are sorted and unique. (R-PB-1)
  _Verified by:_ `pytest -k test_parse_makefile_is_deterministic_with_sorted_unique_targets` · stage: `make test`

- [x] **AC-PB-2 (non-success):** `parse_makefile` raises on no generated
  input, with a BOM, NUL, CRLF or an exotic separator prepended or
  substituted. (R-PB-2)
  _Verified by:_ `pytest -k test_parse_makefile_never_raises_on_arbitrary_text` · stage: `make test`

- [x] **AC-PB-3:** `strip_define_blocks` applied twice equals once, and the
  second pass reports no `define`. (R-PB-3)
  _Verified by:_ `pytest -k test_strip_define_blocks_is_idempotent` · stage: `make test`

- [x] **AC-PB-4:** for a generated upstream delta, the requirement count
  equals the number of requirement headings emitted, at any depth from two
  to four. (R-PB-4)
  _Verified by:_ `pytest -k test_upstream_requirement_count_is_independent_of_heading_depth` · stage: `make test`

- [x] **AC-PB-5 (non-success):** no printable-ASCII recasing or padding of a
  criterion changes `is_negative`. (R-PB-5)
  _Verified by:_ `pytest -k test_is_negative_depends_on_wording_not_casing_or_padding` · stage: `make test`

- [x] **AC-PB-6 (non-success):** the wheel declares no runtime dependency,
  and every new module stays stdlib-only. (C-PB-1)
  _Verified by:_ `pytest -k test_new_modules_stdlib_only` · stage: `make test`

- [x] **AC-PB-7:** every property runs under `PROPERTY_SETTINGS` with
  `derandomize=True`, and none is marked `xfail`. (R-PB-6, C-PB-2)
  _Verified by:_ `pytest -k test_property_settings_are_derandomized_and_nothing_is_xfailed` · stage: `make test`

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-PB-1..7 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, thresholds |
