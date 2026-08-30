# Change: Add `--version`/`-V` CLI Flag

## Why

`planlint`'s argparse setup has no way to print the installed version — a
standard capability for a CLI of this class, and `pyproject.toml` already
carries a version string with nothing exposing it. `-v` is already taken
by `--verbose`, so the short form must be uppercase `-V`.

## What Changes

- `openspec_graph/cli.py`: new `_version_string()` helper resolves the
  version from installed package metadata
  (`importlib.metadata.version("openspec-graph")` — the distribution
  name; *not* `"planlint"`, which is only the console-script name),
  falling back to the package's existing `__version__` constant only when
  running from an uninstalled checkout
  (`importlib.metadata.PackageNotFoundError`). Wired as a standard
  argparse `action="version"` flag (`-V`/`--version`) on the top-level
  parser, alongside `--target`/`--verbose`.

Sourcing the version from installed package metadata is self-correcting
against drift — it can never go stale relative to what's actually
installed — rather than adding a third hardcoded copy alongside
`pyproject.toml`'s `version = "0.1.0"` and `__init__.py`'s
`__version__ = "0.1.0"` (both pre-existing, unrelated, untouched by this
change).

## Non-Goals

- No change to `pyproject.toml`'s or `__init__.py`'s existing version
  constants — this change only adds a new way to *read* the version, not
  a new place it's declared.
- `--version` is a top-level optional flag, not a subcommand — it must
  never be added to or count against `test_cli_surface.py`'s closed
  verb-allow-list guard (AC-RP-3).

## Affected Capabilities

- `cli-version-flag`
