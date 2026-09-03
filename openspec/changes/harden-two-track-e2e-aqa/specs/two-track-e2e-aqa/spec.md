# Spec: Two-Track E2E AQA

> **Change:** `harden-two-track-e2e-aqa`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

Every CI job runs on `ubuntu-latest`, so the platform guard tests this
suite carries — Windows path separators, console encoding, symlink
privilege — are never exercised on the platform they guard. Three defects
shipped green and were caught only by manual Windows runs
(`fix-windows-path-separator-leak`, `fix-stdout-encoding-crash`, and
`test_findings_envelope.py::test_two_checkout_paths_produce_identical_json`'s
raw-native-path `str.replace` against JSON output, which can never match
on Windows because `json.dumps` doubles every backslash). The
encoding-crash fix itself has no CI leg reproducing its failure
environment, so a regression would ship silently the same way the original
did.

Separately, `docs/hooks.md`'s CI hooks table drifted from
`.github/workflows/ci.yml` when the `packaging` job was added: no gate
enforces the correspondence, so the drift was discovered by inspection,
not by a failing check.

And the no-mocks e2e track — the installed `planlint` run against this
live repo, which is what the `self-validate` CI job does — has no single
local entry point; a contributor reproducing it must read the workflow
YAML and retype its steps.

## Requirements

- R-AQA-1: A single Makefile target, `e2e-live`, MUST compose the
  no-mocks live track: `detect`, `validate --fail-on ERROR`,
  `graph --format json`, `waivers`, and one additional
  `validate --fail-on ERROR` pass under an ASCII-only console, all against
  this repository's live tree.
- R-AQA-2: CI MUST run the core gates — lint, typecheck, and the test
  suite including both coverage floors — on `windows-latest`, so the
  platform guard tests execute on the platform they guard.
- R-AQA-3: CI MUST run the live track under an ASCII-only console
  (`PYTHONIOENCODING=ascii`), so the encoding crash's original failure
  environment is itself a gate.
- R-AQA-4: `docs/hooks.md`'s CI hooks table MUST list every job defined
  in `.github/workflows/ci.yml`; the correspondence MUST be enforced by
  the test suite, not by reviewer memory.
- R-AQA-5: The new Makefile target and workflow jobs MUST NOT
  re-introduce a hard-coded coverage floor or tool-version pin
  (G003 / AC-EH-6 stays green).
- C-AQA-1: This change MUST NOT add, rename, or remove any rule, and MUST
  NOT alter `tests/baseline_rules.json`.
- C-AQA-2: `make pre-pr`'s composition MUST NOT change; the live track is
  additive (its own target and CI jobs), not folded into the pre-PR gate.

## Decisions

- **DEC-AQA-001:** the Windows leg pins a single Python 3.12, matching
  `self-validate`'s pin. A full 3.10–3.13 Windows matrix was considered
  and rejected: the Ubuntu `test` matrix already covers interpreter
  breadth, the Windows job exists for *platform* breadth, and Windows
  runner minutes cost multiples of Linux ones. If a Windows-only,
  version-dependent defect ever appears, widening the matrix is a one-line
  change.
- **DEC-AQA-002:** `encoding-stress` runs on Ubuntu, not Windows. The
  original crash environment is faithfully reproduced by
  `PYTHONIOENCODING=ascii` alone — an explicit `PYTHONIOENCODING` is not
  overridden by PEP 538/540 locale coercion — and Ubuntu minutes are
  cheaper. The Windows leg's job is path/separator/privilege coverage;
  the encoding leg's job is the console encoding, and either OS can
  provide it.
- **DEC-AQA-003:** the Windows job installs GNU make via Chocolatey
  (`choco install make -y`) rather than duplicating the Makefile's recipe
  lines into the workflow. GNU make is not preinstalled on the
  `windows-latest` (Server 2022) image, while Chocolatey, Git Bash, and
  the Python toolcache are. Duplicating recipes would fork the single
  source of gate commands the Makefile provides; paying one install step
  keeps `make <target>` the only definition of every gate.
- **DEC-AQA-004:** `e2e-live`'s ASCII pass uses POSIX env-prefix syntax
  (`PYTHONIOENCODING=ascii planlint ...`). Under `cmd`/PowerShell that
  syntax does nothing, so the target's comment tells Windows users to run
  it under Git Bash or set the variable for the whole shell. A
  cross-platform alternative (`python -c` wrapper) would bury the actual
  command being gated.
- **DEC-AQA-005:** guard tests parse `ci.yml`'s job keys structurally
  (line-scan of the `jobs:` mapping — PyYAML is deliberately not a
  dependency, per the zero-runtime-deps contract and `tools/`'s
  stdlib-only rule) instead of substring-matching the YAML text, so a
  cosmetic reformat cannot false-fail them and a renamed job cannot
  false-pass them.

## Acceptance Criteria

- [x] **AC-AQA-1:** `make e2e-live` exists in the Makefile (and its
  `.PHONY` line), and composes the live verbs plus one ASCII-console
  `validate --fail-on ERROR` pass, in one target. (R-AQA-1)
  _Verified by:_ `pytest -k test_makefile_has_e2e_live_target` · stage: `make test`

- [x] **AC-AQA-2:** `.github/workflows/ci.yml` defines a job running on
  `windows-latest` that invokes `make lint`, `make typecheck`, and
  `make test` after installing make. (R-AQA-2)
  _Verified by:_ `pytest -k test_ci_workflow_has_a_windows_job` · stage: `make test`

- [x] **AC-AQA-3:** `.github/workflows/ci.yml` defines a job that sets
  `PYTHONIOENCODING` to an ASCII-only value and runs the live track.
  (R-AQA-3)
  _Verified by:_ `pytest -k test_ci_workflow_has_an_encoding_stress_job` · stage: `make test`

- [x] **AC-AQA-4 (negative):** a job defined in `ci.yml` but missing from
  `docs/hooks.md`'s CI hooks table MUST fail the test suite — the
  `packaging`-job drift this change backfills is a hard error on
  recurrence, never a silent doc gap. (R-AQA-4)
  _Verified by:_ `pytest -k test_hooks_ci_table_lists_every_ci_job` · stage: `make test`

- [x] **AC-AQA-5 (negative):** the new Makefile target and workflow jobs
  carry no coverage-floor literal and no tool-version pin; the
  no-hardcoded-thresholds gate stays green over the edited files.
  (R-AQA-5)
  _Verified by:_ `pytest -k test_no_hardcoded_passes_on_clean_repo` · stage: `make test`

- [x] **AC-AQA-6:** the rule registry and `tests/baseline_rules.json` are
  byte-identical before and after this change. (C-AQA-1)
  _Verified by:_ `pytest -k test_rule_set_matches_baseline` · stage: `make test`

- [x] **AC-AQA-7:** `make pre-pr` still composes exactly `ci typecheck
  security docs-check thresholds` — `e2e-live` is additive, not folded
  into the pre-PR gate. (C-AQA-2)
  _Verified by:_ `pytest -k test_makefile_has_e2e_live_target` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-AQA-1..7 |
| Live | `make e2e-live` | exit 0 on the live repo, including the ASCII pass |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
