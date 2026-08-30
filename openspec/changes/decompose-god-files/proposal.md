# Change: Decompose God Files

## Why

A god-file scan (SQE/SWE/Architect lens) of the merged `main` found that
responsibility boundaries are not reflected in module boundaries. Five
production modules each bundle several unrelated concerns, and four test
modules redeclare the same inline fixtures. Concretely:

- `parse.py` holds two dialect grammars, the shared data model, waiver parsing,
  threshold linting, and heading-drift analysis in one file.
- `rules.py` holds every rule across three families, the driver, and finding
  rendering/serialization.
- `scaffold.py` mixes document templates with filesystem writes.
- `graph.py` has a single function that occupies most of the file and re-does
  detection, parsing, and node assembly.
- `detect.py` bundles five detectors behind one `StackProfile` aggregate.
- Four test files redeclare the same `MAKEFILE` / `PYPROJECT` / spec fixtures.

None of this is a correctness bug — every gate is green — but the concentration
makes the codebase harder to reason about and raises the cost of the next
change. The decomposition is structural only: the public API, CLI output, and
graph JSON stay byte-identical.

## What Changes

- Extract shared test fixtures into `tests/support.py` and `tests/fixtures/`,
  removing the triplicated inline fixture blobs.
- Split `scaffold.py` by extracting its templates into
  `scaffold_templates.py`; keep `scaffold.py` as the write layer.
- Break up `graph.build_graph` into private helper functions; the public
  `build_graph` signature and output are unchanged.
- Split `parse.py` into `parse_model.py` (data model), `parse_harness.py`,
  `parse_upstream.py`, and `parse_semantics.py`, with `parse.py` retained as a
  facade re-exporting the public surface.
- Split `rules.py` into `rule_types.py` (Finding/Rule/severities) and per-family
  modules (`rules_generic`, `rules_harness`, `rules_upstream`), with `rules.py`
  retained as the registry/facade.
- Add guard tests proving public-import compatibility, byte-identical output,
  and import-boundary discipline (parser must not import cli/graph; rule modules
  must not import cli/graph).

## Impact

- Affected: `openspec_graph/{parse,rules,scaffold,graph}.py`, `tests/` suite.
- Backward compatibility: preserved by construction. `openspec_graph/__init__.py`
  re-exports are unchanged; `parse.py` and `rules.py` remain as facades that
  re-export the public symbols tests and call sites already import.
- No new runtime dependencies; all new modules are stdlib-only.
- `detect.py` and `cli.py` are intentionally left intact this pass —
  `StackProfile` is a natural aggregate and `cli.py` is the expected
  orchestration hub.
