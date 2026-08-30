# Changelog

All notable changes to OpenSpec-Graph follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — post-merge quality review (`post-merge-quality-review` change package)

- **Lint hygiene**: `Finding.render` uses `contextlib.suppress(ValueError)`
  (SIM105); `scaffold.plan_init` drops a dead assignment before `return`
  (RET504). Extended ruff families now report zero findings.
- **Type safety**: `graph.build_graph` carries `dict[str, object]` type
  arguments; `mypy --strict` on the package is clean (advisory, not a gate —
  DEC-PR-001).
- **No magic numbers in the graph contract**: node-text truncation is the named
  `NODE_TEXT_LIMIT = 200` constant (preserves the prior value exactly).
- **Reusable gate helpers**: `tools/_common.py` (`repo_root()`, `read_text()`)
  is shared by `check_docs.py`, `check_no_hardcoded_thresholds.py`, and
  `check_secrets.py` via the standalone-script `sys.path` bootstrap — repo-root
  discovery is now defined once.
- **Edge-case tests**: unknown `SPECGRAPH_LOG_LEVEL`, path-outside-root
  fallback, `init --dry-run`, and mixed-dialect warning. Branch coverage
  90.8% → 91.3%.
- **Structural guard tests**: AC-PR-3/4/6/8 are enforced by `make test`, not
  one-off grep — a regression reintroducing a bare `[:200]`, a duplicated
  repo-root literal, a third-party import in `_common.py`, or a forced
  pre-push hook in the Makefile/CI fails the suite. Logging-level assertions
  use `logging.WARNING`/`DEBUG`/`INFO` constants, not magic integers.
- **Docs**: optional pre-push hook in `docs/hooks.md`; deferred hooks/loops
  (watch loop, scheduled self-validation cron, pre-push) and skills/agents
  (entry-point rule registration) extension points in `docs/next-steps.md`.

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
