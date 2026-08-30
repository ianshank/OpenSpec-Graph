# Spec: Enterprise hardening

> **Change:** `enterprise-hardening`
> **Version:** 1.0.0-draft
> **Authors:** SQE / SWE / Architect review
> **Status:** APPROVED

---

## Problem Statement

**Evidence:** `harden-ci-gates` shipped real coverage, lint, and graph-diff
gates, but the pre-merge quality bar is still line/branch/ruff only. An
enterprise AQA suite for a governance CLI needs type safety, secret scanning,
deterministic (byte-stable) validation output, structured debug logging, and
documentation that lets a new contributor reproduce the whole gate locally with
one command. None of that exists yet, and several repo-hygiene gaps remain
(`.ruff_cache` and `coverage.json` appear in the working tree; no
`.dockerignore`, no `CHANGELOG`, no architecture doc).

## Requirements

- R-EH-1: The AQA suite MUST be reproducible from a single `make pre-pr` command.
- R-EH-2: Static type checking MUST be a hard gate (mypy), with config read from
  `pyproject.toml` — no tool version or threshold pinned in the Makefile.
- R-EH-3: Secret scanning (gitleaks) MUST be a hard gate on PRs and locally.
- R-EH-4: Rule-engine and CLI JSON output MUST be deterministic: the same fixture
  tree evaluated twice yields byte-identical, stably-sorted JSON.
- R-EH-5: A `--verbose` / `SPECGRAPH_LOG_LEVEL` debug mode MUST emit diagnostics
  to stderr only; JSON output on stdout MUST remain pure and parseable.
- R-EH-6: No numeric threshold, tool version, or path may be hard-coded in the
  Makefile or CI workflow YAML. Floors live in `pyproject.toml`; the Makefile
  and workflow only name scripts that read them.
- R-EH-7: All public CLI verbs and options from v0.1.0 MUST keep working
  (backward compatibility); existing default stdout contracts MUST NOT change.
- R-EH-8: Documentation MUST let a contributor reproduce the full gate: C4
  architecture, AQA guide, hooks, the rules-as-deterministic-skills model,
  CHANGELOG, and next steps.

## Acceptance Criteria

- [ ] **AC-EH-1:** `make pre-pr` runs test + lint + typecheck + security +
  validate and exits 0 on a clean tree. (R-EH-1)
  _Verified by:_ `make pre-pr` · stage: `make pre-pr`

- [ ] **AC-EH-2 (non-success):** A type error introduced into the package fails
  `make typecheck` non-zero; the error names the file and line. (R-EH-2)
  _Verified by:_ `make typecheck` on a deliberately-broken checkout · stage: `make typecheck`

- [ ] **AC-EH-3 (non-success):** A committed secret fails `make security`
  non-zero and the gitleaks CI job. (R-EH-3)
  _Verified by:_ `make security` on a fixture with a fake key · stage: `make security`

- [ ] **AC-EH-4:** Evaluating the same fixture tree twice and diffing the JSON
  from `validate --json`, `graph --format json`, and `rules --json` yields zero
  diff bytes; ordering is stable (sorted by a deterministic key). (R-EH-4)
  _Verified by:_ `pytest -k deterministic` · stage: `make test`

- [ ] **AC-EH-5 (non-success):** A malformed spec fails `validate` closed
  (non-zero) rather than emitting a partial graph; `--verbose` logs the parse
  path to stderr while stdout stays parseable JSON. (R-EH-5)
  _Verified by:_ `pytest -k verbose_or_closed` · stage: `make test`

- [ ] **AC-EH-6 (non-success):** A numeric threshold found in the Makefile or
  `.github/workflows/ci.yml` fails the no-hardcoded-values check. (R-EH-6)
  _Verified by:_ `tools/check_no_hardcoded_thresholds.py` · stage: `make pre-pr`

- [ ] **AC-EH-7:** Every CLI verb and option documented in v0.1.0 still accepts
  the same arguments and default output format; the existing test suite stays
  green without edits. (R-EH-7)
  _Verified by:_ `pytest tests/ -q` · stage: `make test`

- [ ] **AC-EH-8:** `docs/` contains C4 architecture, AQA guide, hooks,
  rules-as-skills model, CHANGELOG, and next-steps, all linked from README. (R-EH-8)
  _Verified by:_ `make docs-check` · stage: `make docs-check`

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-EH-4, AC-EH-5, AC-EH-7 |
| Static | `make typecheck` | AC-EH-2 |
| Security | `make security` | AC-EH-3 |
| Pre-PR | `make pre-pr` | AC-EH-1, AC-EH-6 |
| Docs | `make docs-check` | AC-EH-8 |

## Open Questions

> [!IMPORTANT]
> **DEC-EH-001 (RESOLVED):** Should Docker be a first-class delivery path or
> an optional reproducible runner? **Decision: optional.** `specgraph` is
> `pip install`-able; Docker is a convenience image for CI sandboxes that want
> a pinned Python. Not required for local dev; the Makefile never depends on
> Docker.
