# Spec: Makefile `define`/`endef` Blocks

> **Change:** `fix-makefile-define-block-misparse`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

A `define...endef` block's body can contain a colon-bearing line at column
0 (no leading tab), which both `machinery.py`'s structural parser and
`detect.py`'s legacy regex fallback previously matched as a real rule
line, fabricating a target that does not exist in the Makefile.

**Evidence:** a fixture `define HELP_TEXT\nUsage: make test\nendef\n`
added `"Usage"` to the resolved target set through both the structural
parser directly and the end-to-end `detect.profile()` path (via the
confidence-triggered legacy widening), before this change.

---

## Requirements

- R-DEF-1: `machinery.parse_makefile` MUST NOT report any line inside a
  `define...endef` block's body as a target, directive, or conditional —
  the entire block body is opaque replacement text.
- R-DEF-2: A `define` block MUST lower `MakefileFacts.confidence` to
  `"low"`, matching the existing precedent for `include`/conditional
  constructs the parser does not fully model.
- R-DEF-3: `detect._legacy_make_targets` (the low-confidence widening
  fallback) MUST NOT fabricate a target from a `define...endef` block's
  body either — fixing the structural parser alone is not sufficient
  end-to-end, since a `define` block's lowered confidence is exactly what
  triggers this fallback to run.
- C-DEF-1: Adding `has_define` to `MakefileFacts` MUST NOT break the one
  existing positional constructor call site.

---

## Acceptance Criteria

- [x] **AC-DEF-1:** A `define` block body line containing a colon does not
  appear in `MakefileFacts.targets`; a real target elsewhere in the file
  still resolves. (R-DEF-1)
  _Verified by:_ `pytest -k test_define_block_body_is_never_parsed_as_a_rule` · stage: `make test`

- [x] **AC-DEF-2:** A directive- or conditional-shaped line inside a
  `define` block does not set `has_include`/`has_conditional`. (R-DEF-1)
  _Verified by:_ `pytest -k test_define_block_suppresses_directive_and_conditional_detection_inside_it` · stage: `make test`

- [x] **AC-DEF-3:** A `define` block sets `has_define = True` and
  `confidence == "low"`. (R-DEF-2)
  _Verified by:_ `pytest -k test_define_block_body_is_never_parsed_as_a_rule` · stage: `make test`

- [x] **AC-DEF-4 (non-success):** A clean Makefile with no `define` block
  still reports `has_define is False` at `"high"` confidence — this change
  never lowers confidence for a file that does not use the construct.
  (C-DEF-1)
  _Verified by:_ `pytest -k test_a_clean_makefile_parses_at_high_confidence` · stage: `make test`

- [x] **AC-DEF-5:** End-to-end through `detect.profile()`, a `define`
  block's body does not leak a fabricated target via the legacy widening
  fallback. (R-DEF-3)
  _Verified by:_ `pytest -k test_define_block_does_not_leak_a_bogus_target_through_the_legacy_widening_fallback` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-DEF-1..5 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
