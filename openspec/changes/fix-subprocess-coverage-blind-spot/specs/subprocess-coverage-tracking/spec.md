# Spec: Subprocess Coverage Tracking

> **Change:** `fix-subprocess-coverage-blind-spot`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`run_cli()` tests the CLI as a real subprocess; with no coverage
subprocess-tracking configuration, every line reachable only through those
calls was invisible to the coverage report regardless of how well it was
actually tested — and that blind spot let a false-negative test and several
untested-but-correct branches go unnoticed.

**Evidence:** before this change, `cli.py`'s `init --dry-run` branch showed
as "missing" in `coverage.json` despite being exercised by
`test_enterprise.py`; after `coverage.process_startup()` wiring, total
coverage rose (96.05% → 96.95%) purely from previously-invisible,
already-tested paths becoming visible — no test logic changed by Milestone 1
alone.

---

## Requirements

- R-CT-1: Coverage measurement MUST include code paths reachable only
  through a `run_cli()`-spawned CLI subprocess, not just the parent pytest
  process.
- R-CT-2: `validate --change <name>` on a repo with a real `openspec/` tree
  but no matching change directory MUST report "no specs found for change",
  distinct from a repo with no `openspec/` tree at all (which MUST report
  "no openspec/ directory").
- C-CT-1: `parse_spec`'s dialect-resolution logic MUST NOT contain an
  unreachable branch.
- R-CT-3: A spec whose repo-level dialect classification is "harness" but
  whose own text is written in upstream form MUST still be parsed
  correctly via the existing per-file fallback, not misreported as having
  no criteria.
- C-CT-2: A malformed `.coveragerc` or `governance-policy.json` MUST NOT
  raise; threshold detection MUST fall through to the next real candidate.
- R-CT-4: A target repo with no Makefile at all MUST resolve to an empty,
  high-confidence `make_targets` set, and MUST NOT cause G004 to fire on a
  spec citing any `make` target.
- C-CT-3: G001 MUST report a distinct message for "neither requirements nor
  criteria recognized" versus "requirements but no criteria" — the two are
  different failures with different fixes.

---

## Acceptance Criteria

- [x] **AC-CT-1:** Total measured coverage after Milestone 1 is not lower
  than before it (subprocess-only paths become visible, none are lost).
  (R-CT-1)
  _Verified by:_ manual `coverage.json` before/after comparison · stage: `make test`

- [x] **AC-CT-2:** `validate --change nope` against a repo with an
  unrelated real change reports "no specs found for change" on stderr, not
  "no openspec/ directory". (R-CT-2)
  _Verified by:_ `pytest -k test_cli_validate_change_not_found` · stage: `make test`

- [x] **AC-CT-3 (non-success):** `validate` against a repo with no
  `openspec/` tree at all still reports "no openspec/ directory" on stderr.
  (R-CT-2)
  _Verified by:_ `pytest -k test_cli_validate_no_openspec_dir` · stage: `make test`

- [x] **AC-CT-4:** `parse_spec`'s dialect-resolution function contains no
  line that cannot execute under any input. (C-CT-1)
  _Verified by:_ manual code trace, full suite unchanged after removal · stage: `make test`

- [x] **AC-CT-5:** A spec classified "harness" whose text is actually
  upstream-form resolves to `dialect == "upstream"` with its requirements
  and criteria recognized, and does not fire G001. (R-CT-3)
  _Verified by:_ `pytest -k test_harness_dialect_falls_back_to_upstream_when_the_text_is_actually_upstream` · stage: `make test`

- [x] **AC-CT-6:** A malformed `governance-policy.json` or `.coveragerc`
  does not raise; `detect` falls through to the next real threshold
  candidate (`pyproject.toml`). (C-CT-2)
  _Verified by:_ `pytest -k test_detect_ignores_malformed` · stage: `make test`

- [x] **AC-CT-7:** A repo with no `Makefile` resolves `make_targets == ()`
  at `"high"` confidence, and a spec citing any `make` target is not
  flagged by G004. (R-CT-4)
  _Verified by:_ `pytest -k test_g004_stays_silent_when_the_target_repo_has_no_makefile_at_all` · stage: `make test`

- [x] **AC-CT-8:** A spec with neither requirements nor criteria fires
  G001 with the "neither...recognized" message, distinct from the
  "requirements but no criteria" message. (C-CT-3)
  _Verified by:_ `pytest -k test_g001_fires_when_neither_requirements_nor_criteria_are_recognized` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-CT-1..8 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
