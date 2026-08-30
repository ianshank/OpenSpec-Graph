# Milestones

## Milestone 1 — Fix the detection gap  [DONE]

- `openspec_graph/detect.py`: new `_read_ini_fail_under(path, section)`
  helper (stdlib `configparser`, `interpolation=None` to avoid an unrelated
  `%` elsewhere in the file raising); `_threshold()` extended with
  `.coveragerc` (`[report]`) then `setup.cfg` (`[coverage:report]`) checks
  after the existing `pyproject.toml` check, with computed
  `.relative_to(root)` locator strings.
- `openspec_graph/parse_semantics.py`: `THRESHOLD_ALLOWLIST` gains
  `.coveragerc` and `setup.cfg`.
- `docs/architecture/c4.md`: invariants section names all three coverage-
  floor locations.
- `tests/test_graft.py`: 5 new tests covering both files, precedence in
  both directions, and the G003 allowlist extension.

- **Gate:** `make pre-pr` green; `planlint validate` clean.
