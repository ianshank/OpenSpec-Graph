# Change: Fix Subprocess Coverage Blind Spot

## Why

`tests/support.py`'s `run_cli()` launches the CLI as a real OS subprocess
(`subprocess.run([sys.executable, "-m", "openspec_graph.cli", ...])`) so
tests can prove real process-level behavior — exit codes, stderr routing,
argument parsing — rather than mocking it away. This is used throughout
`test_enterprise.py`, `test_cli_surface.py`, `test_graft.py`, `test_graph.py`,
`test_decomposition.py`, and `test_ci_hardening.py`. With no
`COVERAGE_PROCESS_START`/`parallel` configuration anywhere in the repo,
pytest-cov was structurally blind to every line reachable only through those
subprocess calls, no matter how thoroughly a test exercised the behavior.

**Evidence:** `cli.py`'s `init --dry-run` branch and its mixed-dialect WARN
print were behaviorally tested via `test_enterprise.py` yet still reported
as "missing" in the coverage output before this change. The previously
reported ~96%/~92% line/branch coverage was therefore a floor, not ground
truth — real coverage of the CLI's subprocess-only paths was unknown.
Fixing the measurement gap (this proposal's Milestone 1) surfaced six real,
previously-invisible gaps by manual reasoning, ahead of and independent of
the tooling fix itself (Milestone 2): a false-negative test that passed for
the wrong reason, one line of dead code, and four genuinely untested — but
correct — branches.

## What Changes

- **Milestone 1 (measurement):** `sitecustomize.py` (new, repo root) calls
  `coverage.process_startup()`; `pyproject.toml` gains
  `[tool.coverage.run] parallel = true` and a `tomli` dev-extra for the
  Python 3.10 CI leg (`coverage` itself declares zero dependencies, and its
  subprocess hook needs a TOML parser for its config file — stdlib
  `tomllib` only covers 3.11+); `tests/support.py`'s `run_cli()` injects
  `COVERAGE_PROCESS_START` into the subprocess environment by default.
  Purely additive — a caller-supplied `env` value for the same key always
  wins, and a normal CLI invocation outside the test suite is unaffected
  (the hook is a no-op when the env var is unset).
- **Milestone 2 (the six gaps the fix surfaced):**
  - A false-negative test (`test_cli_validate_change_not_found`) whose
    fixture never created `openspec/`, so it exercised the wrong guard in
    `cli.py` and would have kept passing even if the guard it was named for
    broke.
  - One line of dead code in `parse.py` (a second, unreachable duplicate of
    an already-normalizing `if` check).
  - Four genuinely correct but untested branches: `parse.py`'s per-file
    harness→upstream misclassification safety net; `detect.py`'s malformed
    `.coveragerc`/`governance-policy.json` fallthrough paths; the
    zero-Makefile end-to-end path through `detect.py` and G004; and G001's
    "neither requirements nor criteria recognized" branch.

## Non-Goals

- No change to any test's *intent* or the CLI's *behavior* beyond the false
  -negative fix (1b) — every other item is a measurement or test-coverage
  fix, not a behavior change.
- No refactor of `run_cli()` to run the CLI in-process instead of as a real
  subprocess — process-level behavior (exit codes, stderr routing, argument
  parsing as an actual OS process) is exactly what these tests are proving,
  and that would be lost by mocking it away.
- Coverage floors in `pyproject.toml` are not touched. If this fix had
  revealed the *true* number below the existing floor, the floor would stay
  put and the newly-visible gaps would be closed instead — as they are,
  here. (In practice the true number was *higher* than previously reported:
  96.05% → 96.95%, since the change makes already-tested paths visible
  rather than removing coverage.)

## Affected Capabilities

- `subprocess-coverage-tracking`
