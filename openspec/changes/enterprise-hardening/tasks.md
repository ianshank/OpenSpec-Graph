# Milestones

## Milestone 1 — AQA gates (mypy, gitleaks, no-hardcoded)  [DONE]

- Added `mypy` to `[dev]` extras; `[tool.mypy]` config (py3.10 target,
  `check_untyped_defs`, `warn_unused_ignores`, `warn_return_any`); `make typecheck`.
- Added `.gitleaks.toml`; `make security` (gitleaks-or-fallback); CI `security` job.
- Added `tools/check_no_hardcoded_thresholds.py` (AC-EH-6); `make pre-pr`.
- **Gate:** `make pre-pr` green; mypy clean (14 files); no-hardcoded passes.

## Milestone 2 — Determinism + logging  [DONE]

- Deterministic JSON: `validate --json`, `graph --format json`, `rules --json`
  are byte-identical on re-evaluation (sorted file discovery, stable rule order).
- `--verbose` / `SPECGRAPH_LOG_LEVEL` debug to stderr only; JSON stdout preserved;
  fail-closed on malformed spec / missing openspec tree.
- **Gate:** `make test` green (97 tests); determinism + verbose tests pass.

## Milestone 3 — Docs + repo hygiene  [DONE]

- `CHANGELOG.md`, `docs/architecture/c4.md`, `docs/aqa.md`, `docs/hooks.md`,
  `docs/agents-skills-harness.md`, `docs/next-steps.md`.
- `.dockerignore` + optional `Dockerfile`; `.pre-commit-config.yaml`.
- Expanded `.gitignore` for logs/artifacts; `tools/check_docs.py`.
- **Gate:** `make docs-check` green; README links all docs.
