# Milestones

## Milestone 1 — Schema + diff engine  [DONE]

- `openspec_graph/dialect_card.py` (new): `SCHEMA_VERSION`,
  `diff_cards(previous, current) -> list[str]`.
- `tests/test_dialect_card.py`: 4 pure unit tests.
- **Gate:** `make test` green.

## Milestone 2 — `StackProfile.to_card()`  [DONE]

- `openspec_graph/detect.py`: `to_card()` method (explicit dict-literal
  reconstruction, excludes `root`, transforms `openspec_root` to
  `has_openspec_root`). Bundled byte-stability cleanup: `_invariants()`'s
  sort key gains a string tie-breaker.
- `tests/test_graft.py`: 2 new tests.
- **Gate:** `make test` green.

## Milestone 3 — CLI wiring  [DONE]

- `openspec_graph/cli.py`: `--format {text,json}` and `--diff PREV_JSON`
  on the `detect` subcommand; `--json` unchanged.
- `tests/test_graft.py`: 7 new tests, including the cross-checkout-path
  portability proof and the read-only guarantee (AC-DC-3) across all
  three output modes.
- **Gate:** `make pre-pr` green; manual spot-check —
  `planlint --target . detect --format json` and a self-diff against this
  repo's own Makefile, confirming `schema_version` present and "no drift."

## Milestone 4 — Change package + docs  [DONE]

- This package, self-dogfooded via `planlint validate`.
- **Gate:** `planlint validate` clean.
