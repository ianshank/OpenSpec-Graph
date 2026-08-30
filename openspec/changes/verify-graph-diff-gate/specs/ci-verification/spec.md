# Spec: CI graph-diff verification

> **Change:** `verify-graph-diff-gate`
> **Version:** 1.0.0-draft
> **Status:** DRAFT

---

## Problem Statement

**Evidence:** the `graph-diff` CI job is configured but not yet exercised on a
real PR. This change package exists only to trigger that job end-to-end.

## Requirements

- R-VDG-1: The graph-diff gate MUST fail a PR that introduces an orphan requirement.

## Acceptance Criteria

- [ ] **AC-VDG-1:** A clean PR (no new orphans) passes the graph-diff job. (R-VDG-1)
  _Verified by:_ `pytest -k test_graph_diff_passes_when_clean` · stage: `make test`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-VDG-1 |
