# Milestones

## Milestone 1 — Rename + alias + positioning  [DONE]

- `pyproject.toml` ships `planlint = "openspec_graph.cli:main"` (primary) and
  `specgraph = "openspec_graph.cli:main_deprecated"` (legacy alias).
- `openspec_graph/cli.py` adds `main_deprecated(argv)`, which prints a one-line
  deprecation to stderr and delegates to `main`, preserving its exit code;
  `prog` and user-facing messages updated to `planlint`.
- `openspec_graph/log.py` renames the logger to `planlint` and accepts both
  `PLANLINT_LOG_LEVEL` (preferred) and `SPECGRAPH_LOG_LEVEL` (legacy).
- `graph.py`, `Makefile`, `.github/workflows/ci.yml`, and `docs/` command
  examples updated from `specgraph` to `planlint`.
- `README.md` rewritten around the wedge with a positioning table and an
  explicit non-goals section.

- **Gate:** `make pre-pr` green; `planlint --target . validate --fail-on ERROR`
  clean.

## Milestone 2 — CLI surface guard  [DONE]

- Added `tests/test_cli_surface.py`: verb allow-list (closed set
  {detect,init,new,validate,graph,rules}), non-success guard against
  authoring verbs, entry-point wiring, and deprecation-alias behavior (warns to
  stderr, preserves failure exit code, keeps stdout JSON parseable, new env
  var works).

- **Gate:** `make test` green; the new spec for this change passes its own
  rules.
