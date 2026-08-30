# Spec: Coverage Floor Detection

> **Change:** `fix-coverage-floor-detection-gap`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`detect._threshold()` only checks governance-policy.json candidates and
`pyproject.toml`. `.coveragerc` and `setup.cfg` — both standard Python
coverage-config locations — are invisible to it, and the gap silently
degrades G003's error message to a generic, non-actionable locator string.

**Evidence:** confirmed by constructing minimal `.coveragerc`- and
`setup.cfg`-based fixtures and running `detect` against them: both silently
returned no threshold found.

---

## Requirements

- R-CF-1: `detect` MUST find a coverage floor declared in `.coveragerc`'s
  `[report]` section when no governance-policy or `pyproject.toml` floor
  exists.
- R-CF-2: `detect` MUST find a coverage floor declared in `setup.cfg`'s
  `[coverage:report]` section under the same condition.
- R-CF-3: When a floor is found in either file, the resulting locator MUST
  name the real file path, not a generic fallback string.
- C-CF-1: `pyproject.toml` MUST continue to take precedence over
  `.coveragerc`/`setup.cfg` when both are present (unchanged, additive-only
  behavior).
- C-CF-2: A spec citing `.coveragerc` or `setup.cfg` by name as its
  threshold source MUST NOT be flagged as a hard-coded threshold.

---

## Acceptance Criteria

- [x] **AC-CF-1:** A repo whose only coverage config is `.coveragerc`
  resolves the real floor value, with a locator naming the real file.
  (R-CF-1, R-CF-3)
  _Verified by:_ `pytest -k test_detect_reads_threshold_from_coveragerc` · stage: `make test`

- [x] **AC-CF-2:** A repo whose only coverage config is `setup.cfg` resolves
  the real floor value, with a locator naming the real file. (R-CF-2, R-CF-3)
  _Verified by:_ `pytest -k test_detect_reads_threshold_from_setup_cfg` · stage: `make test`

- [x] **AC-CF-3:** `.coveragerc` takes precedence over `setup.cfg` when both
  are present. (R-CF-1, R-CF-2)
  _Verified by:_ `pytest -k test_detect_prefers_coveragerc_over_setup_cfg` · stage: `make test`

- [x] **AC-CF-4 (non-success):** `pyproject.toml` keeps winning over
  `.coveragerc` even when both are present — this change never weakens the
  existing precedence. (C-CF-1)
  _Verified by:_ `pytest -k test_detect_still_prefers_pyproject_over_coveragerc` · stage: `make test`

- [x] **AC-CF-5:** A spec citing `.coveragerc` as its threshold source is not
  flagged by G003. (C-CF-2)
  _Verified by:_ `pytest -k test_g003_allows_a_threshold_read_from_coveragerc` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-CF-1..5 |
