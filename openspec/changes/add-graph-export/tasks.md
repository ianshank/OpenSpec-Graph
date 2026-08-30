# Milestones

## Milestone 1 — Graph projection  [DONE]

- Added `openspec_graph/graph.py` exposing `build_graph(profile) -> dict` that
  walks every `change/*/specs/*/spec.md`, returning nodes (spec, requirement,
  criterion, stage, invariant) and edges (traces-to, verified-by, declares,
  finding).
- Added a `graph` subcommand to `cli.py` with `--format json` (default); `--format
  dot` is rejected with a non-zero exit naming rendering as a downstream concern.
- Reuses `detect.profile`, `detect.find_spec_files`, `parse.parse_spec`, and
  `rules.evaluate` directly. No new parser.

- **Gate:** `make validate` green; the new spec for this change passes its own
  rules.

## Milestone 2 — Self-validation and release  [DONE]

- Added `tests/test_graph.py` (22 tests) covering all seven ACs, including the
  two non-success paths (missing tree, unknown stage) and the pure-projection
  agreement with `validate` (AC-GR-4).
- Wired the coverage gate into `make ci` (`--cov --cov-fail-under=90`); total
  coverage is 95.81%, above the floor in `pyproject.toml`.
- Wired `specgraph graph --format json` into the CI self-validation job, emitting
  the repo's own spec graph as a build artifact.

- **Gate:** `make ci` green on the full matrix; the graph artifact is non-empty
  for this repo's own `openspec/` tree.
