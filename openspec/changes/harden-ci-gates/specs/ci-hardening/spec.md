# Spec: CI Hardening

> **Change:** `harden-ci-gates`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

Implementing `add-graph-export` exposed that several CI gates were notional. The
coverage floor existed in `pyproject.toml` but `make ci` never ran coverage, so
debt drifted to 89.29% — below the declared floor — with no failing build. The
lint target silently skips when `ruff` is absent. The spec dependency graph is now
emitted as an artifact but nothing fails if a PR introduces a broken edge.

**Evidence:**
- `Makefile::test` was `pytest tests/ -q` with no `--cov`; the `fail_under` in
  `pyproject.toml:[tool.coverage.report]` was never enforced by `make ci`.
- `Makefile::lint` exits 0 with "ruff not installed, skipping" when ruff is absent.
- `specgraph graph` emits `spec-graph.json` to CI artifacts, but no job diffs it
  against `main`, so a newly-introduced orphan requirement ships unreviewed.

---

## Requirements

- R-CH-1: The system MUST enforce the coverage floor declared in
  `pyproject.toml:[tool.coverage.report].fail_under` on every `make ci` run.
- R-CH-2: The system MUST add a branch-coverage floor, because line coverage
  alone misses untested conditional branches.
- R-CH-3: The system MUST make `ruff` a hard gate: lint fails the build on
  violations and never silently skips.
- R-CH-4: The system MUST fail a PR whose spec graph increases `broken_links` or
  introduces a new orphan requirement, compared to the base branch.
- C-CH-1: The change MUST NOT alter what the rules check, only how CI enforces
  them. No new rules.
- C-CH-2: Coverage floors MUST be read from `pyproject.toml` at run time. No
  literal threshold may appear in this spec or its CI configuration.

## Acceptance Criteria

- [ ] **AC-CH-1:** `make ci` runs coverage with `--cov-fail-under` read from
  `pyproject.toml:[tool.coverage.report].fail_under`, and fails when coverage is
  below the floor. (R-CH-1)
  _Verified by:_ `pytest -k test_ci_enforces_coverage_floor` · stage: `make validate`

- [ ] **AC-CH-2 (non-success):** A coverage drop below the floor fails `make ci`
  with a non-zero exit naming the floor and the actual percentage, rather than
  passing silently. (R-CH-1, C-CH-2)
  _Verified by:_ `pytest -k test_ci_fails_below_coverage_floor` · stage: `make validate`

- [ ] **AC-CH-3:** `make ci` enforces a branch-coverage floor in addition to the
  line-coverage floor. (R-CH-2)
  _Verified by:_ `pytest -k test_ci_enforces_branch_coverage` · stage: `make validate`

- [ ] **AC-CH-4 (non-success):** When `ruff` reports a violation, `make lint`
  exits non-zero and does not print the "skipping" fallback. (R-CH-3)
  _Verified by:_ `pytest -k test_lint_is_a_hard_gate` · stage: `make validate`

- [ ] **AC-CH-5 (non-success):** A PR whose spec graph increases `broken_links`
  over the base branch fails CI, and the failing job names the new broken edges.
  (R-CH-4)
  _Verified by:_ `pytest -k test_graph_diff_fails_on_new_broken_edges` · stage: `make validate`

- [ ] **AC-CH-6 (non-success):** A PR that introduces a new orphan requirement
  fails CI; a PR that fixes an existing orphan requirement passes. (R-CH-4)
  _Verified by:_ `pytest -k test_graph_diff_fails_on_new_orphan` · stage: `make validate`

- [ ] **AC-CH-7:** The graph-diff job uploads `spec-graph.json` and its diff
  against the base branch as a CI artifact on every PR. (R-CH-4)
  _Verified by:_ `pytest -k test_graph_diff_artifact_uploaded` · stage: `make ci`

- [ ] **AC-CH-8:** The rule set is unchanged: the rule IDs and severities reported
  by `specgraph rules` match the base branch, confirming no rules were added or
  removed by this change. (C-CH-1)
  _Verified by:_ `pytest -k test_rule_set_unchanged` · stage: `make validate`

## Invariants Touched

- None. This change hardens CI enforcement of existing rules; it does not touch
  detection, parsing, or rule evaluation.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Spec gate | `make validate` | AC-CH-1..6 pass; this spec itself validates clean |
| Full pipeline | `make ci` | all of the above, plus coverage and branch floors met (AC-CH-7) |

## Backward Compatibility

- The coverage gate now fails builds that previously passed with debt below the
  floor. This is intended: the floor was always declared; it was simply not
  enforced. Teams with debt below the floor must raise coverage before merging.
- The lint gate now fails on violations where it previously skipped. This is
  intended: a soft pass is not a gate.

## Open Questions

> [!IMPORTANT]
> **DEC-CH-001 (RESOLVED):** Should the graph-diff gate compare against
> `origin/main`, or against the PR's merge-base? **Decision: the merge-base.** A
> graph-diff gate's job is to catch drift THIS PR introduces. Comparing against
> `origin/main` would flag drift from rebases or other merged PRs that aren't
> this PR's responsibility — false positives that block PRs for changes they
> did not make. The merge-base isolates the PR's own effect. No longer blocking.
