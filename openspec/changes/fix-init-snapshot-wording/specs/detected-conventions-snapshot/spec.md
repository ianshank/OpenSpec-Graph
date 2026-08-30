# Spec: Detected-Conventions Snapshot Wording

> **Change:** `fix-init-snapshot-wording`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`init`-generated content and CLI help text claimed `specgraph.json`/
`project.md` "pin" or are "authoritative" for detected conventions, but no
code path ever reads either file back — `detect` always re-derives fresh.
The wording overclaimed behavior the tool does not have.

**Evidence:** grep across `detect.py`, `cli.py`, and `scaffold.py` found
zero read sites for either file; `scaffold.py`'s generated `project.md`
nonetheless told every scaffolded repo "this file is authoritative."

---

## Requirements

- R-SNAP-1: Every user-facing description of `specgraph.json`/`project.md`
  (generated content, CLI help text, README) MUST describe them as a
  snapshot recorded at `init` time, not as a live config or override.
- C-SNAP-1: `detect` MUST continue to re-derive every convention fresh
  from the filesystem on every run — this change corrects wording only,
  it does not add a read-back path.

---

## Acceptance Criteria

- [x] **AC-SNAP-1:** The generated `project.md` content describes itself
  as a snapshot, not as authoritative, and explicitly states that editing
  it does not change enforcement. (R-SNAP-1)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-SNAP-2:** `cli.py`'s module docstring and `init`'s `--help`
  text both describe `init` as writing a snapshot, not pinning
  conventions. (R-SNAP-1)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-SNAP-3:** `README.md`'s `init` usage example comment matches.
  (R-SNAP-1)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-SNAP-4 (non-success):** `detect.profile()`'s behavior is
  unchanged — the full test suite passes with no test modified by this
  change, confirming no read-back path was accidentally introduced.
  (C-SNAP-1)
  _Verified by:_ `make test` (full suite, unmodified) · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Docs | `make docs-check` | AC-SNAP-1..3 (manual review; a wording-only change has no automated content check, matching `fix-adopter-artifact-drift`'s precedent) |
| Full | `make pre-pr` | AC-SNAP-4 — full regression unchanged |
