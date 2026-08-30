# Milestones

## Milestone 1 — Track subprocess coverage  [DONE]

- `sitecustomize.py` (new, repo root): calls `coverage.process_startup()`,
  a no-op unless `COVERAGE_PROCESS_START` is set.
- `pyproject.toml`: `[tool.coverage.run] parallel = true`; `tomli` added as
  a `python_version < "3.11"` dev extra.
- `tests/support.py`: `run_cli()` injects `COVERAGE_PROCESS_START` into the
  subprocess env by default (caller-supplied `env` always wins).
- `Makefile`: `lint` covers `sitecustomize.py`; `clean` removes
  `.coverage.*` parallel-mode data files.
- **Gate:** `make test` green; total coverage not lower than before
  (96.05% → 96.95% observed).

## Milestone 2 — Close the six newly-visible gaps  [DONE]

- `tests/test_graph.py`: fixed `test_cli_validate_change_not_found`'s
  false-negative fixture; tightened `test_cli_validate_no_openspec_dir`'s
  unused `capsys` into a real assertion.
- `openspec_graph/parse.py`: removed the unreachable duplicate `if`
  branch at the old lines 68-69.
- `tests/test_graft.py`: added
  `test_harness_dialect_falls_back_to_upstream_when_the_text_is_actually_upstream`,
  `test_detect_ignores_malformed_governance_policy_json`,
  `test_detect_ignores_malformed_coveragerc`,
  `test_g004_stays_silent_when_the_target_repo_has_no_makefile_at_all`,
  `test_g001_fires_when_neither_requirements_nor_criteria_are_recognized`.
- **Gate:** `make pre-pr` green; `planlint validate` clean.
