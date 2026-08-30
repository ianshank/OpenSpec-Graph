# Change: Add Dialect Cards (CP-2)

## Why

`docs/differentiation-roadmap.md` names CP-2 as the next v1 feature to
build after CP-1 (rename, shipped) and CP-3 (structural Makefile parsing,
shipped): `detect` becomes a product, not just an internal helper — a
machine-readable **dialect card** (stages, threshold locator, invariant
source, languages, dialect) as stable JSON, so a CI job can diff the card
and turn silent house-style drift into a finding.

`StackProfile.as_dict()` already carries nearly everything a card needs,
but it also carries `root` (and, less obviously, `openspec_root` — always
exactly `root / "openspec"` when set) — both absolute filesystem paths
that differ across every checkout, machine, or CI runner. A `--diff` built
naively on top of the existing `as_dict()` output would report constant,
meaningless "drift" on `root` alone, on every single invocation from a
different location, defeating the feature's entire purpose. This is why
the card must be a deliberately narrower, portable projection of
`StackProfile`, not `as_dict()` verbatim.

## What Changes

- New `openspec_graph/dialect_card.py`: `SCHEMA_VERSION` constant and
  `diff_cards(previous, current) -> list[str]`, a pure, stdlib-only,
  zero-intra-package-import module (mirrors `machinery.py`'s precedent),
  reusing `tools/diff_spec_graph.py`'s existing `diff(...) -> list[str]`
  shape and `PASS:`/`FAIL:` vocabulary for consistency.
- `StackProfile.to_card()` (`detect.py`): everything `as_dict()` carries
  except `root`, with `openspec_root` reduced to a portable
  `has_openspec_root: bool` (the presence/absence signal is real
  drift-worthy information — dropping it entirely would lose signal, not
  just an absolute path), plus a `schema_version` field.
- `cli.py`'s `detect` subcommand gains `--format {text,json}` (the `json`
  choice emits the card) and `--diff <prev.json>` (loads a previous
  card's JSON, diffs against the current one, exits non-zero and lists
  changed fields on drift). The existing `--json` flag is untouched —
  still the full `as_dict()`, including `root`, for backward
  compatibility.

## Non-Goals

- No change to `--json`'s existing output shape. `--json` and
  `--format json` are intentionally two different, differently-named,
  differently-shaped outputs — `--json` for the full local profile,
  `--format json`/`--diff` for the portable card — mitigated with
  distinct help text on each rather than trying to unify them, since
  AC-DC-1 names `--format json` as the card's entry point specifically.
- No new `tools/` script for the diff. `--diff` lives as a `detect` flag
  because the roadmap's AC-DC-2 pins that interface explicitly; only the
  diff *pattern* (a pure `diff(...) -> list[str]` function, `PASS`/`FAIL`
  vocabulary) is reused from `tools/diff_spec_graph.py`, not the mechanism.
- No CI wiring for `--diff` (a job mirroring the existing `graph-diff`
  job) — not required by any of CP-2's three ACs; a natural follow-up
  once the CLI capability has shipped and proven useful, not bundled in.
- No extensibility for `detect.py`'s hardcoded discovery lists
  (`INVARIANT_SOURCES`, `MANIFESTS`, the inline `policy_candidates`) —
  unrelated to this change's scope; tracked separately in
  `docs/next-steps.md` if it becomes worth doing.

## Affected Capabilities

- `dialect-cards`
