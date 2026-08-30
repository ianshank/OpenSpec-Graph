# Spec: U004 Body Check

> **Change:** `fix-u004-body-blind-modal-check`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

Rule U004 only inspects a requirement's heading line for SHALL/MUST, never
its body prose, because the parser's capture group cannot cross a newline.
The common real-world authoring style — a short noun-phrase heading with the
normative sentence in the paragraph below — always false-fires.

**Evidence:** confirmed against a real external repo: 20 of 34 requirements
across 4 change packages incorrectly WARN today, all textbook-normative
requirements with the modal verb in the body rather than the heading.

---

## Requirements

- R-UB-1: The system MUST recognize a SHALL/MUST modal verb anywhere in a
  requirement's heading or body prose (upstream dialect), not the heading
  alone.
- R-UB-2: A requirement whose heading and body both lack a modal verb MUST
  still fail U004.
- C-UB-1: The harness dialect's requirement construction MUST NOT be
  affected by this change.

---

## Acceptance Criteria

- [x] **AC-UB-1:** A requirement with a normative body but a non-normative
  heading does not trigger U004. (R-UB-1)
  _Verified by:_ `pytest -k test_u004_does_not_fire_when_the_modal_verb_is_only_in_the_body` · stage: `make test`

- [x] **AC-UB-2 (non-success):** A requirement with neither a normative
  heading nor a normative body still triggers U004. (R-UB-2)
  _Verified by:_ `pytest -k test_u004_fires_on_a_non_normative_requirement` · stage: `make test`

- [x] **AC-UB-3:** Harness-dialect specs are unaffected by this change; the
  full suite stays green. (C-UB-1)
  _Verified by:_ `make test` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-UB-1..3 |
