# Change: Rename CLI and Positioning (`planlint`)

## Why

The product's wedge is "the CI gate that fails when a spec cites a gate this
repo does not have." The command name `specgraph` undersells that wedge and
carries the word "graph" the differentiation strategy explicitly retires. A
clearer command name plus an explicit positioning statement (wedge, comparison,
non-goals) is what lets `planlint` be "the thing you point at someone else's
clone."

**Evidence:** `pyproject.toml:[project.scripts]` ships a single `specgraph`
entry point; `README.md` describes the tool as a "dependency graph for specs"
rather than a CI gate; no guard prevents authoring verbs from creeping into the
CLI surface.

## What Changes

- Rename the console-script entry point `specgraph` → `planlint` (primary).
- Keep `specgraph` as a backwards-compatible alias that prints a one-line
  deprecation to **stderr** and delegates to `main`, preserving the real exit
  code (never silently passing CI).
- Rewrite `README.md` around the wedge; add a positioning table and an explicit
  non-goals section.
- Add `tests/test_cli_surface.py` — a verb allow-list guard (closed CLI surface)
  plus deprecation-alias behavior tests.

## Non-Goals

- No rename of the waiver comment syntax (`<!-- specgraph:allow ... -->`), the
  config file (`openspec/specgraph.json`), or the `[tool.specgraph]` pyproject
  section. Those are stable contract identifiers already in user repos;
  renaming them is a migration, not a CLI rename.
- No new verbs. The CLI surface is a closed read/lint set.
- No PyPI publication in this change; install is from source / GitHub until a
  release is cut.

## Affected Capabilities

- `cli-positioning`
