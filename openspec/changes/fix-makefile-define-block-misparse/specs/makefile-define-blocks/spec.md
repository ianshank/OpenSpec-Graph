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

**Round 2 (found by independent adversarial review, before merge):** the
initial fix for the above introduced its own regressions. Most serious:
`detect.py`'s define-block-stripping regex
(`r"^define\b.*?^endef\b.*?$"`, `re.MULTILINE|re.DOTALL`) was
quadratic-time on an *unterminated* `define` block — benchmarked at 32+
seconds on a 20K-line adversarial input, directly reachable since an
unterminated block lowers confidence and unconditionally triggers this
exact code path. Also found: nested `define` blocks (legal GNU Make,
verified against a real `make` binary) fabricated a target from the inner
block's body; a space-indented `endef` (also legal) was hidden by a
recipe-line skip that ran before the in-block check, silently losing
every real target for the rest of the file; and a `\b` word-boundary
check matched at a word-to-hyphen transition, misreading a real target
literally named `define-thing:` as a directive.

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
- R-DEF-4: Parsing an unterminated `define` block MUST complete in time
  linear in the input size — no whole-text regex with unbounded lazy
  matching over an untrusted, possibly-unterminated block.
- R-DEF-5: Nested `define` blocks MUST resolve at the matching *outer*
  `endef`, not the first `endef` encountered (a depth counter, not a
  boolean).
- R-DEF-6: An `endef` line indented with leading whitespace MUST still
  close its block — the in-block check MUST run before, not after, any
  recipe-line (leading-whitespace) skip.
- R-DEF-7: The `define`/`endef` keyword match MUST require whitespace or
  end-of-line after the keyword, not merely a `\b` word boundary, so a
  real target name that happens to start with `define`/`endef` followed
  by a non-word, non-whitespace character (e.g. a hyphen) is never
  misread as the keyword.
- C-DEF-2: `machinery.py` and `detect.py` MUST share a single
  `define`/`endef`-block-stripping implementation — the round-2 bugs
  above stemmed directly from having two independent, separately-buggy
  copies of this logic.

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

- [x] **AC-DEF-6:** An unterminated `define` block (20K lines, no
  matching `endef`) parses in well under 5 seconds, both directly via
  `machinery.parse_makefile` and end-to-end via `detect.profile()` — a
  generous, CI-safe wall-clock bound proving linear rather than
  quadratic time, without asserting a specific complexity class
  directly. (R-DEF-4)
  _Verified by:_ `pytest -k test_unterminated_define_block_does_not_scale_quadratically or test_unterminated_define_block_does_not_hang_detect_end_to_end` · stage: `make test`

- [x] **AC-DEF-7:** A `define` block nested inside another `define` block
  resolves only at the matching outer `endef`; a body line between the
  inner and outer `endef` is never parsed as a real target. (R-DEF-5)
  _Verified by:_ `pytest -k test_nested_define_blocks_resolve_at_the_outer_endef_not_the_inner_one` · stage: `make test`

- [x] **AC-DEF-8:** A leading-whitespace-indented `endef` still closes
  its block; a real target appearing after it is not lost. (R-DEF-6)
  _Verified by:_ `pytest -k test_space_indented_endef_still_closes_the_block` · stage: `make test`

- [x] **AC-DEF-9 (non-success):** A real target literally named
  `define-thing:` parses as a target, not as a `define` directive.
  (R-DEF-7)
  _Verified by:_ `pytest -k test_hyphenated_target_name_starting_with_define_is_not_a_directive` · stage: `make test`

- [x] **AC-DEF-10:** `machinery.py` and `detect.py` call the identical
  `machinery.strip_define_blocks` implementation — no second, independent
  copy of this logic exists in the codebase. (C-DEF-2)
  _Verified by:_ `pytest -k test_strip_define_blocks_is_directly_testable_and_reused_by_both_parsers` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-DEF-1..10 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
