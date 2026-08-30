# Milestones

## Milestone 1 — Real coverage gate

- Add `pytest-cov` as a dev dependency in `pyproject.toml`.
- Switch the `test` make target to run `--cov --cov-fail-under` against the
  locator in `pyproject.toml:[tool.coverage.report].fail_under`.
- Add a branch-coverage floor in `[tool.coverage.report]` (line coverage alone
  misses untested conditional branches).

- **Gate:** `make ci` green; coverage meets both the line and branch floors.

## Milestone 2 — Lint is a hard gate

- Add `ruff` as a dev dependency so the lint target never silently skips.
- Remove the "skipping" fallback from the `lint` make target.

- **Gate:** `make lint` fails the build when ruff reports violations; no soft pass.

## Milestone 3 — Spec-graph diff gating

- Add a CI job that runs `specgraph graph --format json` on the PR branch and on
  `origin/main`, and fails if `broken_links` increased or a new orphan
  requirement appeared.
- The diff is uploaded as an artifact for review.

- **Gate:** `make ci` green; a PR that adds a broken edge or orphan requirement
  fails CI.
