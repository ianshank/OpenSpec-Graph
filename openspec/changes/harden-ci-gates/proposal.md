# Change: Harden CI Gates

## Why

Implementing `add-graph-export` exposed that several CI gates were notional
rather than real. The coverage floor existed in `pyproject.toml` but `make ci`
never ran coverage, so debt accumulated to 89.29% — below the 90% floor — without
any build failing. The lint step silently skips when `ruff` is absent. The spec
dependency graph is now emitted as an artifact but nothing fails if a PR
introduces a broken edge or an orphan requirement.

**Evidence:**
- Before this work, `make ci`'s `test` target was `pytest tests/ -q` with no
  `--cov`; the `fail_under = 90` in `pyproject.toml` was never enforced, and
  total coverage had drifted to 89.29% (`cli.py` at 67%).
- `Makefile::lint` prints "ruff not installed, skipping" and exits 0 when ruff
  is absent — a soft pass, not a gate.
- `specgraph graph` emits `spec-graph.json` to CI artifacts, but no job diffs it
  across a PR, so a newly-introduced orphan requirement or unknown make stage
  ships without review.

## What Changes

- Make the coverage gate real and add a branch-coverage floor (line alone misses
  untested conditional branches).
- Make `ruff` a dev dependency so lint is a hard gate, never silently skipped.
- Add a CI job that diffs `spec-graph.json` against `main` and fails if a PR
  increases `broken_links` or introduces a new orphan requirement.

## Non-Goals

- No change to detection, parsing, or rule evaluation.
- No new rules. This hardens how existing rules are enforced in CI, not what they check.
- No enforcement of coverage on unchanged lines (a changed-lines gate is a
  separate, larger change — see Open Questions).

## Affected Capabilities

- `ci-hardening`
