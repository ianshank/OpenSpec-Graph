# Spec: CLI Version Flag

> **Change:** `add-cli-version-flag`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`planlint` had no `--version`/`-V` flag; a contributor or CI script had no
way to ask the installed CLI what version it is without reading
`pyproject.toml` directly.

---

## Requirements

- R-VER-1: `planlint --version` and `planlint -V` MUST print a version
  string to stdout and exit 0.
- R-VER-2: The version MUST be read from installed package metadata
  (self-correcting against drift), not a third hardcoded literal.
- R-VER-3: `--version`/`-V` MUST work with no subcommand present — it
  short-circuits before the required-subcommand check.
- C-VER-1: `--version` MUST NOT be registered as a subcommand — it is a
  top-level optional flag like `--target`/`--verbose`, and must never
  expand `test_cli_surface.py`'s closed verb allow-list (AC-RP-3).

---

## Acceptance Criteria

- [x] **AC-VER-1:** `planlint --version` exits 0 with non-empty stdout.
  (R-VER-1)
  _Verified by:_ `pytest -k test_version_flag_prints_version_and_exits_zero` · stage: `make test`

- [x] **AC-VER-2:** `-V` produces byte-identical output to `--version`.
  (R-VER-1)
  _Verified by:_ `pytest -k test_short_version_flag_matches_long_form` · stage: `make test`

- [x] **AC-VER-3:** `--version` works with no subcommand argument present
  (no "usage"/argparse-error text on stderr). (R-VER-3)
  _Verified by:_ `pytest -k test_version_flag_does_not_require_a_subcommand` · stage: `make test`

- [x] **AC-VER-4 (non-success):** If package metadata cannot be found (an
  uninstalled checkout), version resolution falls back to the package's
  own `__version__` constant rather than raising. (R-VER-2)
  _Verified by:_ `pytest -k test_version_string_falls_back_when_package_metadata_is_unavailable` · stage: `make test`

- [x] **AC-VER-5 (non-success):** `"version"` never appears in the CLI's
  registered subcommand set. (C-VER-1)
  _Verified by:_ `pytest -k test_version_flag_is_not_a_registered_subcommand` · stage: `make test`

- [x] **AC-VER-6:** The distribution name is resolved dynamically via
  `importlib.metadata.packages_distributions()` from the importable
  package name, not a second hardcoded copy of `pyproject.toml`'s
  `[project]` name — a distinct failure mode (the top-level package
  simply absent from that mapping) also falls back to `__version__`
  rather than raising. (R-VER-2)
  _Verified by:_ `pytest -k test_version_string_falls_back_when_top_level_package_is_unmapped` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-VER-1..6 |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
