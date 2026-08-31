# Milestones

## Milestone 0 — Design + adversarial review  [DONE]

- Designed as one of four CPs planned together (architecture drift, witness
  mode, policy packs, visualization); adversarial review found and fixed a
  real bug (`DEC-GV-001`) before any code was written.

## Milestone 1 — `mermaid.py` pure module  [DONE]

- New `openspec_graph/mermaid.py::to_mermaid(graph: dict) -> str`, pure,
  stdlib-only, zero intra-package import (mirrors `dialect_card.py`'s
  precedent).
- Synthetic node ids (real ids contain slashes/dots); orphan/missing node
  classes; broken-edge `linkStyle`.
- 14 pure unit tests (`tests/test_mermaid.py`); added to
  `tests/test_decomposition.py::_NEW_MODULES`.
- **Gate:** `make pre-pr` green; 100% line/branch coverage on the new module.

## Milestone 2 — `--change` scoping + `--format mermaid` wiring  [DONE]

- `build_graph()` gains an optional `spec_files` param scoping rendering
  only — `rules.evaluate_tree()` always sees the full, unscoped tree
  (`DEC-GV-001`/`DEC-GV-002`).
- `detect.filter_by_change()` extracted, shared by `cmd_validate` and
  `cmd_graph` (`DEC-GV-004`).
- `cli.py`: `graph` gains `--change` and a `mermaid` `--format` choice;
  `--format dot`'s rejection is unrevised (`DEC-GV-003`).
- 8 new tests in `tests/test_graph.py`: mermaid end-to-end, dot-rejection
  regression guard, `--change` rendering scope, the false-orphan regression
  guard, the genuine-orphan-still-surfaces guard, not-found/no-openspec-dir
  errors, and a pure `filter_by_change()` unit test.
- **Gate:** `make pre-pr` green; `planlint validate` clean.

## Milestone 3 — companion `tools/render_mermaid.py`  [DONE]

- Thin script rendering a saved `graph --format json` file, importing
  `mermaid.to_mermaid()` directly rather than duplicating it (a deliberate,
  first-of-its-kind exception among `tools/` scripts, documented in the
  script's own docstring).
- 2 new tests in `tests/test_ci_hardening.py`, mirroring
  `diff_spec_graph.py`'s own test precedent exactly.
- **Gate:** `make pre-pr` green; manual dogfood spot-check:
  `planlint --target . graph --change <real-change> --format mermaid`
  against this repo's own tree.
