# Changelog

All notable changes to OpenSpec-Graph follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — enterprise hardening (`enterprise-hardening` change package)

- **`make pre-pr`**: one-command enterprise AQA gate (test + lint + typecheck +
  security + validate + docs-check + no-hardcoded-thresholds).
- **mypy** as a hard type-checking gate (`make typecheck`), config in
  `pyproject.toml` (`check_untyped_defs`, `warn_unused_ignores`).
- **gitleaks** secret scanning (`make security`) with a deterministic Python
  fallback when the binary is absent; `.gitleaks.toml` config; CI gitleaks job.
- **`tools/check_no_hardcoded_thresholds.py`**: fails if a numeric threshold or
  tool version is hard-coded in the Makefile or workflow YAML.
- **`tools/check_docs.py`**: fails if a required doc is missing or unlinked from
  README.
- **Structured debug logging**: `-v` / `--verbose` and `SPECGRAPH_LOG_LEVEL`
  emit diagnostics to stderr only; JSON stdout stays pure and parseable.
- **Deterministic JSON output** for `validate --json`, `graph --format json`,
  and `rules --json` (stable ordering), with regression tests locking it in.
- **Optional `Dockerfile`** + `.dockerignore` for hermetic CLI invocation.
- **`.pre-commit-config.yaml`** wiring ruff, mypy, gitleaks, and self-validation.
- Documentation: C4 architecture (`docs/architecture/c4.md`), AQA guide
  (`docs/aqa.md`), hooks (`docs/hooks.md`), the rules-as-deterministic-skills
  model (`docs/agents-skills-harness.md`), and next steps (`docs/next-steps.md`).

## [0.1.0] — 2026-08-30

### Added

- `specgraph` CLI: `detect`, `init`, `new`, `validate`, `graph`, `rules`.
- Rule engine: 16 rules (G001–G005, H001–H006, U001–U005) across harness and
  upstream dialects, with inline waiver support.
- Scaffolded OpenSpec change packages; graph export (pure projection of
  `validate`); `harden-ci-gates` coverage/lint/graph-diff gates.
- GitHub Actions CI: test matrix (3.10–3.13), self-validate hard gate,
  graph-diff regression gate on PRs.

[Unreleased]: https://github.com/ianshank/OpenSpec-Graph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ianshank/OpenSpec-Graph/releases/tag/v0.1.0
