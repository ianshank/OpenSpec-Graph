# Spec: Demo Capability

> **Status:** DRAFT

## Problem Statement

**Evidence:** `demo/mod.py::run` writes without attestation.

## Requirements

- R-DMO-1: The system MUST attest every write.
- C-DMO-1: The change MUST NOT weaken INV-1.

## Acceptance Criteria

- [ ] **AC-DMO-1:** An attested write records an evidence id. (R-DMO-1)
  _Verified by:_ `pytest -k test_attested_write` · stage: `make regression`

- [ ] **AC-DMO-2 (non-success):** An unattested write is denied and the
  error names INV-1. (C-DMO-1)
  _Verified by:_ `pytest -k test_unattested_denied` · stage: `make regression`

## Invariants Touched

- INV-1: preserved, proven by AC-DMO-2.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make regression` | AC-DMO-1..2 |
