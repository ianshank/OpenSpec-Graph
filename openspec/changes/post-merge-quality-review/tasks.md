# Tasks — Post-Merge Quality Review

- [x] Run objective scans: extended ruff, `mypy --strict` (advisory), coverage
      gaps, duplication/hardcoded-value grep.
- [x] Apply ruff cleanups: `contextlib.suppress(ValueError)` in `Finding.render`;
      drop dead assignment in `scaffold.plan_init`.
- [x] Add `dict[str, object]` type args to `graph.build_graph`; name the
      `NODE_TEXT_LIMIT = 200` constant.
- [x] Extract `tools/_common.py` (`repo_root()`, `read_text()`); wire the three
      gate scripts via the standalone-script `sys.path` bootstrap.
- [x] Add targeted edge-case tests: unknown log level, path-outside-root
      fallback, `init --dry-run`, mixed-dialect warning.
- [x] Document the optional pre-push hook in `docs/hooks.md`.
- [x] Document deferred hooks/loops + skills/agents extension points in
      `docs/next-steps.md`.
- [x] Create this change package; set Status APPROVED.
- [x] Verify `make pre-pr` green; push; open PR; confirm CI green.
