# Change: Add a Versioned, Portable `validate --json` Envelope

## Why

`validate --json` is the one output this project tells adopters to persist
and read on a *different* machine from the one that produced it — and it is
the only structured output with neither a schema version nor a portable
path. Its payload is `{target, specs_checked, findings, blocking}`, and each
`findings[].path` is `str(self.path)`: an absolute, native-separator path to
a directory that exists only on the runner that produced it.

**Evidence:** `.github/workflows/ci.yml:62-72` runs
`planlint --target . validate --fail-on WARN --json > spec-findings.json`
and then uploads `spec-findings.json` via `actions/upload-artifact@v4` — as
does the adopter-facing `templates/spec-gate.yml:44-52`, and its
byte-identical twin `skills/planlint-spec-governance/assets/spec-gate.yml`
that ships inside the distributed Agent Skill. An uploaded artifact is by
construction read somewhere other than the runner: every `path` in it points
at `/home/runner/work/<repo>/<repo>/openspec/...`, a directory the reader
does not have. The same skill's `SKILL.md:38-40` already draws the
distinction this change acts on — it recommends `detect --format json` as
"a portable, schema-versioned dialect card" and warns that `detect --json`
is "a legacy shape carrying machine-specific absolute paths" — while
`validate --json`, the output it recommends in the same sentence, is neither
portable nor schema-versioned.

Nothing has been published yet: `CHANGELOG.md`'s `[0.2.0]` header records
that `v0.1.0` "was never published to a package index" and that `v0.2.0` is
"the first intended for PyPI; publication happens when the tag is pushed."
So this is a free correction today and a breaking change for real adopters
the day after the first release — which is the whole argument for doing it
now rather than agreeing it is right and deferring it.

**This supersedes a recorded decision, deliberately.**
`openspec/changes/fix-windows-path-separator-leak/specs/windows-path-separators/spec.md`'s
`DEC-PS-002` excluded `Finding.as_dict()`'s `path` field from that fix on
purpose, reasoning that absolute self-referential fields are "never compared
across two checkouts of the same repo: two developers' or two CI runners'
absolute paths to 'this repo' never match to begin with, so posix-normalizing
them buys no portability," and concluding that `as_dict()`'s `path` field "is
*always* absolute … so there is no normally-relative case for its separator
to be consistent with. Fixing `as_dict()` 'for consistency' would in fact
introduce the inconsistency, not remove one." That decision is pinned by a
live test,
`tests/test_enterprise.py::test_finding_as_dict_path_field_stays_absolute_and_native`,
which this change **keeps**: its subject is the default rendering, and the
default is what survives.

The new evidence is the CI template, which `DEC-PS-002` did not consider: its
first argument's premise is not that two machines' absolute paths *match*, it
is that nobody ever *carries the value to a second machine*. The
`upload-artifact` step in both workflows falsifies exactly that premise — the
value is produced on a runner and read off it. That is the argument this
change defeats.

`DEC-PS-002`'s **second** argument — that a field which is always absolute
has no normally-relative case for its separator to be consistent with — is
**not** defeated, and the design respects it rather than overriding it. The
new `root` parameter is opt-in and defaults to `None`, so `as_dict()`'s own
default rendering stays absolute and native-separator for every caller that
does not ask otherwise. Inside this package there is exactly one caller —
`cli.cmd_validate`'s `--json` branch — and it always passes a root. The
outside-root fallback is posix only within the branch that already
relativizes, so consistency-within-the-method holds in both directions.
`DEC-PS-002`'s other two subjects — `StackProfile.root`/`openspec_root` and
`validate --json`'s top-level `target` — are likewise not overturned and are
not touched here; `target` in particular must stay absolute, because it is
the base the new relative paths resolve against.

Two smaller defects are in the same blast radius and fixed with it:

- `validate --json` emits findings in raw evaluation order while the
  plain-text branch sorts them (`cli.py:321-334`, `_sort_key`). Two
  renderings of one run disagree on order, and the JSON one is unstable
  under any future change to spec-discovery order.
- `detect --json` (`cli.py:506-507`, help text: "legacy; unchanged shape")
  selects `StackProfile.as_dict()`, whose `root`/`openspec_root`/
  `speckit_root` fields are machine-specific absolute paths. Removing the
  flag after publication is a break; saying so before publication is free.

## What Changes

- **`openspec_graph/rule_types.py`** — `Finding.as_dict()` gains an optional
  `root: Path | None = None`. When `root` is given, `path` is rendered with
  `detect.to_posix_relative(self.path, root)` — the helper this module
  already imports and already uses in `Finding.render()`. When `root` is
  `None` the output is byte-identical to today's, so no other caller
  changes. A new module-level `FINDINGS_SCHEMA_VERSION = 1` is declared
  beside `Finding` and added to `__all__`, mirroring
  `dialect_card.SCHEMA_VERSION` and `witness.WITNESS_SCHEMA_VERSION`.
- **`openspec_graph/rules.py`** — re-exports `FINDINGS_SCHEMA_VERSION` in
  its facade `__all__`, so `cli.py` reaches it through `rules.` like every
  other rule-layer name it uses (R-DG-1's facade discipline).
- **`openspec_graph/cli.py`** —
  - `_version_string()` is split: a new, `@functools.cache`d
    `_package_version() -> str` performs the distribution lookup and returns
    a bare version string; `_version_string()` becomes
    `f"%(prog)s {_package_version()}"`, keeping the argparse `%(prog)s` token
    at the argparse boundary where it belongs. No second lookup path is
    introduced, and the cache is what makes the lookup run once per run:
    argparse resolves `version=_version_string()` on every invocation of
    every verb, and `cmd_validate` then needs the same value again, so
    without it the ambiguous-environment `WARNING:` printed twice in a single
    `validate --json` — measured, not hypothesized.
  - `cmd_validate`'s `--json` branch emits
    `{schema_version, tool_version, target, specs_checked, findings,
    blocking}` — `schema_version` from the constant, `tool_version` from
    `_package_version()`, `target` unchanged and still absolute, the other
    three keys unchanged in spelling and meaning. `findings` becomes
    `[f.as_dict(prof.root) for f in sorted(findings, key=_sort_key)]`.
  - `_sort_key` is lifted out of `cmd_validate`'s body to a module-level
    helper taking `(finding, root)` (or a closure factory), so the JSON and
    text branches provably share one ordering rather than two copies.
  - `cmd_detect`'s `if args.json:` branch prints exactly one deprecation
    line to **stderr** before dumping the payload; stdout stays
    byte-identical.
- **`tests/test_decomposition.py`** — `_run_cli()` normalizes the
  `tool_version` value the way it already normalizes the root path
  (`<ROOT>`), so a version bump never re-pins the hash again;
  `_EXPECTED_HASHES["validate"]` is re-pinned once, in this change, for the
  envelope itself. `["graph"]`/`["rules"]` are untouched.
- **`tests/test_enterprise.py`** —
  `test_finding_as_dict_path_field_stays_absolute_and_native` is **kept**,
  with its comment block rewritten to record which half of `DEC-PS-002` was
  superseded and which still stands, and joined by
  `test_finding_as_dict_with_a_root_renders_posix_relative` for the other
  half of the contract.
- **`tests/test_findings_envelope.py`** (new) — the envelope's own suite:
  the six keys and their spellings, the schema and tool versions, `target`
  staying absolute, every finding path relative and POSIX, two checkouts
  producing identical JSON, the shared sort order, the non-success trio
  (outside-root emitted, `None` path stays `null`, clean repo reports an
  empty list), the three `detect --json` deprecation cases, and
  `test_package_version_is_the_single_lookup_site`, which runs
  `validate --json` in a subprocess with two distributions patched in and
  asserts the ambiguity warning appears exactly once.
- **`tests/conftest.py`** — an autouse fixture clearing
  `cli._package_version`'s cache around every test, so a memoized value
  cannot leak between in-process tests that patch `importlib.metadata`.
- **`CHANGELOG.md`** — an `[Unreleased]` entry recording the envelope, the
  path change as a deliberate supersession of `DEC-PS-002`, and the
  `detect --json` deprecation with its removal target of `1.0`.
- **`skills/planlint-spec-governance/SKILL.md`** — the structured-output
  paragraph is updated so `validate --json` is described as
  schema-versioned and target-relative, since it currently recommends it
  in the same breath as the portability warning it fails.

## Non-Goals

- **No key renames.** `specs_checked` and `blocking` keep their spellings
  even though neither is an obvious name; renaming is a second break that
  buys nothing and would make the schema version's first bump carry two
  unrelated migrations for a consumer.
- **No relativization of `target`, `StackProfile.root`, or
  `StackProfile.openspec_root`.** `DEC-PS-002`'s reasoning still holds for
  these — `target` is the base the relative paths resolve against, so it
  must stay absolute to keep the payload self-describing.
- **No schema version for `graph --format json`, `waivers --format json`, or
  `rules --json`.** They have the same gap; `graph`'s output is also
  uploaded by `ci.yml`. They are excluded because the path-portability
  argument differs per output (graph already relativizes via
  `graph._relative_to`) and bundling three envelope changes into one would
  make a single golden-hash re-pin cover three unrelated shape changes.
  Tracked separately.
- **No published JSON Schema file, and no `$schema` key.** An integer
  version consumers can compare is what `dialect_card`/`witness` already
  established as this project's convention; a schema document is a
  distribution and maintenance commitment this change does not make.
- **No removal of `detect --json` in this change.** It is deprecated in
  words, with a stated removal target of `1.0`, and its stdout stays
  byte-identical — an adopter who ignores stderr sees no change at all.
- **No change to any exit code, to the plain-text `validate` output, or to
  `json.dumps`'s `indent=2`/`ensure_ascii` behavior.** The only text-branch
  effect is that its sort key now lives at module level.

## Affected Capabilities

- `findings-envelope`
