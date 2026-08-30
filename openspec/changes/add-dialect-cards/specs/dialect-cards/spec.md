# Spec: Dialect Cards

> **Change:** `add-dialect-cards`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`detect` had no stable, machine-readable, portable output a CI job could
diff to catch silent drift in a repo's detected conventions. The existing
`as_dict()` output includes absolute paths (`root`, `openspec_root`) that
differ across every checkout/machine/CI run, so it cannot be diffed
directly without producing constant false "drift."

**Evidence:** `StackProfile.as_dict()`'s `root` field is `str(self.root)`
where `root = root.resolve()` — always absolute. `openspec_root` is always
exactly `root / "openspec"` when set, inheriting the same problem.

---

## Requirements

- R-DC-1: `detect --format json` MUST emit a schema-versioned card
  excluding every absolute-path-derived field.
- R-DC-2: Re-running `--format json` on an unchanged repo, or on the same
  logical repo at a different absolute location, MUST be byte-identical.
- R-DC-3: `detect --diff <prev.json>` MUST exit non-zero and list every
  changed field when conventions drift, and exit 0 with no drift.
- C-DC-1: The existing `--json` flag's output shape MUST NOT change.
- C-DC-2: `detect` MUST continue to write nothing to the target repo,
  across every output mode (text, `--json`, `--format json`).

---

## Acceptance Criteria

- [x] **AC-DC-1:** `detect --format json` emits a stable dialect card with
  a schema version; re-running on an unchanged repo is byte-identical.
  (R-DC-1, R-DC-2)
  _Verified by:_ `pytest -k test_detect_format_json_emits_a_dialect_card_with_schema_version or test_detect_format_json_is_byte_identical_across_runs` · stage: `make test`

- [x] **AC-DC-2:** `detect --diff <prev.json>` exits non-zero and lists
  changed fields when the repo's detected conventions drift. (R-DC-3)
  _Verified by:_ `pytest -k test_detect_diff_exits_nonzero_and_lists_changed_fields_on_drift` · stage: `make test`

- [x] **AC-DC-3 (non-success):** `detect` writes nothing to the target
  repo, across text, `--json`, and `--format json` modes. (C-DC-2)
  _Verified by:_ `pytest -k test_detect_never_writes_to_the_target_repo` · stage: `make test`

- [x] **AC-DC-4:** The card is byte-identical for the same logical repo at
  two different absolute checkout paths — the strongest proof that no
  machine-specific field leaks through. (R-DC-1, R-DC-2)
  _Verified by:_ `pytest -k test_detect_format_json_card_is_identical_across_different_checkout_paths` · stage: `make test`

- [x] **AC-DC-5 (non-success):** The existing `--json` flag keeps emitting
  the full, unchanged profile (including `root`) — this change is
  additive, never a breaking replacement. (C-DC-1)
  _Verified by:_ `pytest -k test_detect_json_flag_still_emits_full_profile_unchanged` · stage: `make test`

- [x] **AC-DC-6 (non-success):** `detect --diff` exits 0 with a `PASS`
  message when there is no drift. (R-DC-3)
  _Verified by:_ `pytest -k test_detect_diff_exits_zero_on_no_drift` · stage: `make test`

- [x] **AC-DC-7 (non-success):** A missing or unreadable `--diff` baseline
  is a usage error (exit 2), not a crash. (R-DC-3)
  _Verified by:_ `pytest -k test_detect_diff_with_missing_baseline_is_a_usage_error` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-DC-1..7 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
