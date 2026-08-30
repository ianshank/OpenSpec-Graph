# Milestones

## Milestone 1 — Add the flag  [DONE]

- `openspec_graph/cli.py`: `_version_string()` helper
  (`packages_distributions()`-resolved installed-metadata first,
  `__version__` fallback); wired as `-V`/`--version` on the top-level
  parser.
- `tests/test_cli_surface.py`: 6 new tests (prints + exits 0, `-V` matches
  `--version`, no-subcommand short-circuit, not a registered subcommand,
  and both `__version__`-fallback failure modes: `PackageNotFoundError`
  and an unmapped top-level package).

- **Gate:** `make pre-pr` green; `planlint validate` clean.
