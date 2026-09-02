# Project conventions

Detected by `planlint` — correct anything wrong, this file is authoritative.

- Spec dialect: `harness`
- Coverage floor source: `pyproject.toml:[tool.coverage.report].fail_under`
- Focused gate: `make validate`
- Full gate: `make ci`
- Invariant source: `(none found)`

## Rules

1. Thresholds are read from the coverage floor source above. Never hard-coded in a spec.
2. Every criterion names a stage that exists in the Makefile.
3. Every spec carries at least one non-success criterion.
4. A `(BLOCKING)` open question keeps the spec at `Status: DRAFT`.
