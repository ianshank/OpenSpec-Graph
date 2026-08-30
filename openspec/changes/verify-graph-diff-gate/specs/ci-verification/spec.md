# Spec: CI graph-diff verification

> **Change:** `verify-graph-diff-gate`
> **Version:** 1.0.0-draft
> **Status:** DRAFT

---

## Problem Statement

**Evidence:** the `graph-diff` CI job is configured but not yet exercised on a
real PR. This change package exists only to trigger that job end-to-end. It is
intentionally a WARN-only regression (H002): self-validate (`--fail-on ERROR`)
passes, but graph-diff must fail because the PR introduces a new broken edge.

## Requirements

- R-VDG-1: The graph-diff gate MUST fail a PR whose spec graph regresses.

## Acceptance Criteria

- [ ] **AC-VDG-1:** A clean PR (no new broken edges) passes the graph-diff job. (R-VDG-1)
  _Verified by:_ `pytest -k test_graph_diff_passes_when_clean` · stage: `make test`

- [ ] **AC-VDG-2 (non-success):** A PR that introduces a broken edge fails the graph-diff job. (R-VDG-1)
  _Verified by:_ `pytest -k test_graph_diff_fails_on_new_broken_edges` · stage: `make test`

- [ ] **AC-VDG-3:** A regression-free spec graph passes the diff. (R-VDG-1)
  _Verified by:_ `pytest -k test_graph_diff` · stage: `make test`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-VDG-1..2 |
