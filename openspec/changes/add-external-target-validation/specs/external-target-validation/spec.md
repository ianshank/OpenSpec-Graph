# Spec: External-Target Validation (XTV)

> **Change:** `add-external-target-validation`
> **Version:** 1.0.0
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

This tool's stated purpose is being safe to point at a repository its author
does not own. That safety property is currently asserted in prose and
demonstrated only against corpora this repository controls, and the rule engine
has never been run against a change-package shape different from its own.

**Evidence:** `openspec_graph/detect.py`'s module docstring states detection is
read-only by contract so that `planlint detect` is always safe to run against an
unfamiliar clone, but no test patches the process-execution or socket surface to
prove it; the nearest precedent, AC-MP-2, covers `machinery.py` alone.
`scaffold.plan_change()` emits exactly three files and
`test_apply_is_idempotent_and_refuses_to_clobber` pins that count, while
`ianshank/Agents` documents a five-file package shape in its `openspec/README.md`.
`rules_harness._missing_sections` (H006) checks a hardcoded set of four section
names, and `detect.detect_dialect` returns `mixed` when both dialect markers
appear across a repository — a state `cmd_detect` reports as a plain print rather
than a finding.

---

## Requirements

- R-XTV-1: Every read-only verb MUST be proven not to invoke a subprocess, open
  a socket, or modify the target tree, by an executable test rather than by
  inspection or docstring.
- R-XTV-2: A tree-modification check MUST compare a hash of the target before and
  after, so that a write followed by a restore does not pass.
- R-XTV-3: The fixture corpus MUST include a change-package shape carrying files
  beyond the three this repository emits, so H006 and dialect detection are
  exercised against a foreign convention.
- R-XTV-4: A failing fixture MUST be produced by targeted mutation of a passing
  fixture rather than authored independently, so the two cannot drift.
- R-XTV-5: A false positive found against an external corpus MUST be filed as its
  own change package, and MUST NOT be patched inside this one.
- C-XTV-1: This change MUST NOT add an authoring verb, and MUST NOT introduce any
  path by which the evaluator proposes rather than evaluates (planlint INV-16).
- C-XTV-2: No target repository under legal hold is in scope for this change.

---

## Acceptance Criteria

- [ ] **AC-XTV-1 (non-success):** With `subprocess.run` and `subprocess.Popen`
  patched to raise, `detect`, `validate`, and `graph` complete against a fixture
  target; removing the patches and introducing a deliberate process call makes the
  test fail. (R-XTV-1)
  _Verified by:_ `pytest -k test_verbs_never_invoke_a_subprocess` · stage: `make test`

- [ ] **AC-XTV-2 (non-success):** With socket creation patched to raise, the same
  three verbs complete; a deliberate outbound call in the same test raises rather
  than succeeding quietly. (R-XTV-1)
  _Verified by:_ `pytest -k test_verbs_never_open_a_socket` · stage: `make test`

- [ ] **AC-XTV-3:** A hash of the target tree is identical before and after each
  verb, and a fixture that writes then restores a file still fails the check.
  (R-XTV-2)
  _Verified by:_ `pytest -k test_target_tree_hash_is_unchanged_and_restore_does_not_pass` · stage: `make test`

- [ ] **AC-XTV-4:** A five-file change package carrying `design.md` and
  `review.md` alongside the three canonical files is classified by
  `detect_dialect` and validated without error, and the resulting classification
  is recorded. (R-XTV-3)
  _Verified by:_ `pytest -k test_five_file_package_shape_classifies_and_validates` · stage: `make test`

- [ ] **AC-XTV-5 (non-success):** H006 does not report a missing section for a
  file the section set was never designed to cover, and still reports one for a
  capability spec genuinely missing a required section. (R-XTV-3)
  _Verified by:_ `pytest -k test_h006_scopes_required_sections_to_capability_specs` · stage: `make test`

- [ ] **AC-XTV-6:** Each of the sixteen rules has one passing and one failing
  fixture, and every failing fixture is derived from its passing counterpart by a
  single targeted mutation. (R-XTV-4)
  _Verified by:_ `pytest -k test_every_rule_has_a_mutated_negative_fixture` · stage: `make test`

- [ ] **AC-XTV-7 (non-success):** An external corpus run that produces findings
  does not modify the external clone; the clone's hash is unchanged and no change
  package in this repository is edited as part of the run. (R-XTV-5, C-XTV-2)
  _Verified by:_ `pytest -k test_external_corpus_run_modifies_neither_tree` · stage: `make validate`

- [ ] **AC-XTV-8 (non-success):** The rejected-verb guard still fails the build
  when any of the five forbidden authoring verbs is added to the CLI surface.
  (C-XTV-1)
  _Verified by:_ `pytest -k test_cli_rejects_authoring_verbs` · stage: `make test`

---

## Invariants Touched

- planlint INV-16 — the evaluator proposes nothing. Preserved by C-XTV-1 and
  guarded by AC-XTV-8. Note this identifier is local to this repository; Mango
  declares a different INV-16 concerning the cognitive/execution boundary, and
  the two must not be cited interchangeably.

---

## Decisions

- **DEC-XTV-001 (resolved):** The read-only guarantee is proven by patching the
  process-execution and socket surfaces, not by auditing imports. A `subprocess`
  import guard cannot catch an `os.system` call and neither catches a socket.
- **DEC-XTV-002 (resolved):** `ianshank/Agents` is the external corpus for this
  change because it is Apache-2.0, owned by the same author, carries no legal
  encumbrance, and authors OpenSpec packages in a shape this repository does not
  produce. No repository under legal hold is used.
- **DEC-XTV-003 (resolved):** Whether a five-file shape warrants a new dialect is
  deliberately left open. This change gathers the evidence; a later change
  decides.

---

## Non-Success Criteria (what this change rejects)

- A read-only claim resting on a docstring, an import audit, or reviewer
  inspection is rejected (AC-XTV-1, AC-XTV-2, DEC-XTV-001).
- A tree-modification check that a write-then-restore can pass is rejected
  (AC-XTV-3).
- Hand-authored failing fixtures that can drift from their passing counterparts
  are rejected (AC-XTV-6).
- Patching an externally-discovered false positive inside this change package is
  rejected; it is filed separately or not at all (R-XTV-5).
- Any use of a repository under legal hold as a target is rejected (C-XTV-2).

---

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Unit | `make test` | AC-XTV-1 through AC-XTV-6, AC-XTV-8 |
| Focused | `make validate` | AC-XTV-7; this package validates clean against its own rules |
| Full | `make ci` | No regression in the existing suite, lint, type-check, or the decomposition-guard hash pins |
| Pre-submission | `make pre-pr` | All of the above green |
