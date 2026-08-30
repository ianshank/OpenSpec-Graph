# Spec: Machinery Parsing (CP-3, design)

> **Change:** `parse-repo-machinery-structurally`
> **Version:** 0.1.0-draft
> **Authors:** maintainer · reviewer
> **Status:** DRAFT

---

## Problem Statement

`detect.py` and `parse_semantics.py` find Makefile targets and hard-coded
thresholds in spec prose by regex over text. This produces real false
positives, and the roadmap's own suggested fix for the Makefile side —
shelling out to real `make` — would introduce a genuine safety regression
against this project's own stated purpose.

**Evidence:** `_MAKE_TARGET.findall("foo bar: baz\n")` returns `[]` — a
multi-target Makefile line silently loses every target, not just one,
confirmed by direct execution against the current regex. `MAKE_REF` matches
the bare word "make" anywhere in spec prose, so the ordinary English verb
"make" followed by a word like "sure" or "progress" false-cites a target.
Separately: GNU Make evaluates
`$(shell ...)` calls outside a recipe body at parse/read time,
unconditionally, and `-p` alone still attempts to build the default goal
(only `make -qp` together avoids that) — so no flag combination makes
shelling out to real `make` safe against an untrusted target repo's
Makefile. See the parent proposal's Why section for full citations.

---

## Requirements

- R-MP-1: A structural Makefile parser MUST resolve target names declared on
  a shared, multi-target line (`foo bar: baz`) as distinct targets, not drop
  them.
- R-MP-2: A structural Makefile parser MUST NOT invoke the `make` binary, or
  any subprocess, under any confidence level or fallback condition.
- R-MP-3: When structural parsing cannot confidently resolve a target (due
  to variable expansion, an `include` directive, or a conditional block), the
  system MUST fall back to the existing regex-based detection rather than
  guess, and MUST surface this as a non-blocking, low-confidence signal, not
  a hard G004 failure.
- R-MP-4: A hard-coded-threshold check MUST suppress a finding only when
  exactly one threshold-shaped number appears on the offending line and it
  matches the real configured value — not when the real value merely appears
  somewhere in a line that also contains other, unrelated numbers.
- R-MP-5: The `make`-citation regex in spec prose MUST require
  backtick-fencing or the existing `stage:` convention, not match a bare
  occurrence of the English word "make".
- C-MP-1: `StackProfile.as_dict()`'s `make_targets` field MUST keep its
  existing `tuple[str, ...]` shape regardless of how the values are computed,
  so no downstream JSON contract or decomposition-guard hash changes.

---

## Acceptance Criteria

- [ ] **AC-MP-1:** A Makefile fixture with a shared multi-target line
  (`lint typecheck: build`) resolves both `lint` and `typecheck` as real
  targets under structural parsing. (R-MP-1)
  _Verified by:_ pytest fixture, new test module · stage: `make test`

- [ ] **AC-MP-2:** A Makefile fixture whose target-position text contains a
  `$(shell touch <marker>)`-style payload never causes the marker to be
  created when parsed — proven by an executable test, not a code-review
  claim. (R-MP-2)
  _Verified by:_ pytest, patches subprocess to raise if called · stage: `make test`

- [ ] **AC-MP-3:** A Makefile fixture containing an `include` directive or a
  target-position variable expansion (`$(BINARY): $(SRCS)`) is parsed with a
  lowered confidence signal and falls back to the existing regex path,
  instead of raising or silently guessing. (R-MP-3)
  _Verified by:_ pytest fixture · stage: `make test`

- [ ] **AC-MP-4 (non-success):** A spec citing a `make` target that is
  genuinely absent from the target repo's Makefile still fails G004 at both
  high and low parser confidence — structural parsing must never weaken the
  rule, only remove false positives. (R-MP-1, R-MP-3)
  _Verified by:_ pytest fixture, asserts G004 still fires · stage: `make test`

- [ ] **AC-MP-5:** A spec line containing two threshold-shaped numbers, only
  one of which matches the real configured floor, still fails G003 for the
  non-matching number — the same-line collision case. (R-MP-4)
  _Verified by:_ pytest fixture · stage: `make test`

- [ ] **AC-MP-6 (non-success):** A spec using the ordinary English verb
  "make" ahead of a plain word, with no backtick-fencing or `stage:`
  convention, does not trip G004 once the citation regex is tightened.
  (R-MP-5)
  _Verified by:_ pytest fixture · stage: `make test`

- [ ] **AC-MP-7:** `StackProfile.as_dict()`'s `make_targets` field is
  byte-identical in shape before and after this change lands, for a fixed
  input Makefile. (C-MP-1)
  _Verified by:_ pytest, extends the decomposition-guard pattern · stage: `make test`

---

## Decisions

- **DEC-MP-001 (resolved):** No subprocess/shell-out to `make`, ever, at any
  confidence level — not primary, not fallback. GNU Make's parse-time
  `$(shell ...)` evaluation makes every flag combination unsafe against an
  untrusted Makefile; see the proposal's Why section. This overrides the
  roadmap sketch's literal "`make -p` parse or a minimal recipe parser"
  suggestion — the minimal recipe parser is not an alternative, it is the
  only acceptable design.
- **DEC-MP-002 (resolved):** Conditional blocks (`ifeq`/`ifdef`) are handled
  by scanning both branches and unioning their targets, not by evaluating
  the condition (impossible without a real evaluator) or ignoring the block
  (risks a false negative that fails a legitimate spec). This deliberately
  biases toward false negatives on "target doesn't exist" — never toward
  wrongly claiming a real target is missing.
- **DEC-MP-003 (resolved):** No new rule ID (e.g. `G006`) is reserved by
  this design. `G006` is already earmarked by the roadmap's
  `add-waiver-ledger-and-inv-lints` change; a low-confidence signal from
  this change can start as an unnumbered diagnostic (precedent:
  `cmd_detect`'s existing dialect-mismatch warning) and only become a
  numbered rule if that turns out to be needed once built.
- **DEC-MP-004 (open, non-blocking):** Whether `%`-pattern rules
  (`%.o: %.c`) should be explicitly excluded from resolved targets (matching
  today's incidental regex behavior, but as a documented, tested decision
  rather than an accident) is left to the implementation to decide and test,
  not fixed by this design.

## Non-Success Criteria (what this change rejects)

- A design or implementation that shells out to `make` in any form,
  regardless of flags, is rejected outright (AC-MP-2, DEC-MP-001).
- A design that weakens G004 for targets structural parsing cannot resolve —
  rather than falling back to today's existing detection — is rejected
  (AC-MP-4).
- A design that suppresses G003 based on value presence anywhere in a line,
  rather than single-unambiguous-match, is rejected (AC-MP-5).

---

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-MP-1..7 |
| Full | `make pre-pr` | No regression in the existing test suite, lint, type-check, or the decomposition-guard hash pins |
