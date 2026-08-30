# Milestones

## Milestone 1 — Graph projection

- Add `openspec_graph/graph.py` exposing `build_graph(profile) -> dict` that
  walks every `change/*/specs/*/spec.md`, returning nodes and edges as a
  plain dict.
- Add a `graph` subcommand to `cli.py` with `--format json` (default) writing to
  stdout; `--format dot` is explicitly out of scope and rejected.
- Reuse `detect.profile`, `detect.find_spec_files`, and `parse.parse_spec`
  directly. Do not re-parse.

- **Gate:** `make validate` green; the new spec for this change passes its own
  rules.

## Milestone 2 — Self-validation and release

- Add `test_graph.py` covering: empty repo, one spec, multiple changes, a spec
  with an orphan requirement (the graph surfaces it as an edge to nothing).
- Wire `graph` into the CI self-validation job so the repo's own spec graph is
  emitted as a build artifact.
- Confirm the coverage floor in `pyproject.toml:[tool.coverage.report].fail_under`
  is met, not lowered.

- **Gate:** `make ci` green on the full matrix; the graph artifact is non-empty
  for this repo's own `openspec/` tree.
