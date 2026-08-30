# Milestones

## Milestone 1 — Real coverage gate  [DONE]

- Added `pytest-cov` to the `[dev]` extras; `make ci` installs `[dev]`.
- Switched the `test` make target to run `--cov --cov-fail-under` read from
  `pyproject.toml:[tool.coverage.report].fail_under`. Line coverage is 94.92%.
- Added `tools/check_branch_coverage.py` enforcing a branch-coverage floor
  (`branch_fail_under = 80`) read from pyproject at run time; branch coverage is
  91.1% (184/202).

- **Gate:** `make ci` green; coverage meets both the line (90) and branch (80)
  floors.

## Milestone 2 — Lint is a hard gate  [DONE]

- Added `ruff` to the `[dev]` extras; CI installs it.
- Removed the "skipping" fallback from the `lint` make target — it now fails on
  violations and exits non-zero when ruff is absent.

- **Gate:** `make lint` is a hard gate; `ruff check` passes clean.

## Milestone 3 — Spec-graph diff gating  [DONE]

- Added `tools/diff_spec_graph.py` that fails non-zero when `broken_links`
  increases or a new orphan requirement appears (base -> head).
- Added a `graph-diff` CI job (PR only) that builds the graph on the PR head and
  on the merge-base (DEC-CH-001), diffs them, and uploads both as an artifact.
- Added `tests/baseline_rules.json` + a test asserting the rule set is unchanged
  (AC-CH-8 / C-CH-1).

- **Gate:** `make ci` green; a PR that adds a broken edge or orphan requirement
  fails CI. Resolved DEC-CH-001: compare against the merge-base.
