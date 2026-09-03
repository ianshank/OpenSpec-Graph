# Milestones

## Milestone 1 — `e2e-live` Makefile target [DONE]

- `Makefile`: new `e2e-live` target (plus `.PHONY` and `help` text)
  composing `detect`, `validate --fail-on ERROR`, `graph --format json`,
  `waivers`, and one `PYTHONIOENCODING=ascii planlint --target . validate
  --fail-on ERROR` pass. No numeric literals on recipe lines
  (G003 / AC-EH-6).
- **Gate:** `python tools/check_no_hardcoded_thresholds.py` green;
  `pytest -k test_makefile_has_e2e_live_target` green.

## Milestone 2 — CI legs for the OS and the encoding the guards exist for [DONE]

- `.github/workflows/ci.yml`: `test-windows` job — `windows-latest`, Git
  Bash shell, `choco install make -y` (make is not preinstalled on the
  Windows runner image), then `make lint` / `make typecheck` / `make test`
  on Python 3.12 (DEC-AQA-001, DEC-AQA-003).
- `.github/workflows/ci.yml`: `encoding-stress` job — `ubuntu-latest`,
  job-level `PYTHONIOENCODING=ascii` / `PYTHONUTF8=0`,
  `pip install -e .`, then `make e2e-live` (DEC-AQA-002).
- **Gate:** `pytest -k "test_ci_workflow_has_a_windows_job or test_ci_workflow_has_an_encoding_stress_job"`
  green; no `fail-under` literal or tool pin introduced.

## Milestone 3 — Guard tests [DONE]

- `tests/test_ci_hardening.py`: `test_makefile_has_e2e_live_target`,
  `test_ci_workflow_has_a_windows_job`,
  `test_ci_workflow_has_an_encoding_stress_job`,
  `test_hooks_ci_table_lists_every_ci_job`. Job names parsed structurally
  out of the workflow's `jobs:` mapping (line scan; PyYAML stays out of
  the tree) — no substring matching (DEC-AQA-005).
- **Gate:** all four pass against the real files;
  `test_hooks_ci_table_lists_every_ci_job` was observed failing on
  `['encoding-stress', 'test-windows']` before the docs fix landed.

## Milestone 4 — Docs sync [DONE]

- `docs/hooks.md`: CI table gains `packaging` (backfilled — the drift this
  package's guard test now fences), `test-windows`, and `encoding-stress`.
- `docs/aqa.md`: new "Two-track e2e" section defining the with-mocks /
  without-mocks split, `make e2e-live`, and the no-`make` reproduction.
- `CHANGELOG.md`: `### Added —` entry under `[Unreleased]`.
- **Gate:** `make docs-check` green; hooks-table guard test green.

## Milestone 5 — Change package dogfood [DONE]

- This package itself: proposal, tasks, and
  `specs/two-track-e2e-aqa/spec.md` with `AC-AQA-1..6`, two non-success
  criteria (AC-AQA-4, AC-AQA-5), and every `_Verified by:` citing a test
  that exists (`tests/test_spec_test_citations.py` enforces this).
- **Gate:** `planlint --target . validate --fail-on ERROR` exit 0;
  `tests/baseline_rules.json` untouched (C-AQA-1); `make pre-pr` green.
