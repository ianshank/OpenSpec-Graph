# Change: Add Delta Lint (CP-5)

## Why

`docs/differentiation-roadmap.md` names CP-5 as the last v1 feature, and states
the user story in one sentence: "you changed the coverage floor; here are the 7
specs that still cite the old number." Today nothing answers that question. A
spec that hard-codes `80%` after the floor moved to `90%` was *correct when it
was written* and is *wrong now*, and no verb says so — `validate` will report
it (G001) with no indication that the machinery moved underneath it, and a
spec that cites a make target deleted last week is indistinguishable from one
that never cited a real target at all.

**Evidence:** both halves of the answer already exist in this package and
nothing joins them. `dialect_card.diff_cards(previous, current)` answers "what
changed in the machinery" and is already wired to `detect --diff`
(`cli.cmd_detect`). `ParsedSpec` carries `make_refs`, `invariant_refs`,
`adr_refs`, and `hard_coded_thresholds` (`openspec_graph/parse_model.py`) —
"what does this spec cite". But every rule that reads those fields compares
them against the *live* profile only: `rules_generic._unknown_make_target`
takes `known = set(profile.make_targets)`, `_unknown_invariant` reads
`profile.invariant_ids`, `_hard_coded_threshold` reads
`profile.threshold.value`. No module in `openspec_graph/` ever accepts a
previous card and a current profile together, so no code path can attribute a
stale citation to the machinery change that made it stale.

The roadmap sketches this verb as `delta --since <ref>`. That form was
**rejected** in a peer-reviewed planning pass before any code was written, for
three independent reasons recorded in `DEC-DL-001`: reading machinery at an old
git ref requires a second `subprocess` call site whose safety argument
(`detect._current_sha`'s docstring: "the argument vector is a fixed literal
with no target-controlled input") does not survive taking a user-supplied ref;
`detect.profile()` takes a filesystem root and its `_threshold`/`_invariants`/
`_adrs` helpers are multi-file discovery over that root, not single files a
`git show` could hand back; and "since a ref" is already available for free by
composing two things that exist — `git worktree add /tmp/base "$BASE"` followed
by `planlint --target /tmp/base detect --format json`, exactly the pattern
`.github/workflows/ci.yml`'s graph-diff job already uses. The shipped form is
therefore `planlint delta --baseline CARD.json`, over a saved
`detect --format json` card — the same saved-card idiom `detect --diff` already
established.

## What Changes

- **`openspec_graph/delta.py`** (new): a frozen `DeltaEntry` dataclass with
  `as_dict()` (mirroring `ledger.LedgerEntry`), a `DELTA_SCHEMA_VERSION`
  constant, and `build_delta(baseline, profile, specs, root)` returning a
  stable-ordered `list[DeltaEntry]`. Pure and stdlib-only: no `subprocess`, no
  file I/O, no git — the same posture as `ledger.py` and `dialect_card.py`.
  It reuses `dialect_card.diff_cards` for the "what changed in the machinery"
  half rather than re-deriving it.
- **`openspec_graph/cli.py`**: new `cmd_delta` plus a `p_delta` subparser
  (`--baseline PREV_CARD_JSON` required, `--format {text,json}`,
  `--dialect`). The baseline read, its error handling, and the exit codes are
  the CLI layer's job, exactly as `cmd_waivers` owns reading `openspec/` for
  `ledger.py`.
- **`tests/test_cli_surface.py`**: `ALLOWED_VERBS` gains `"delta"` — the verb
  allow-list is a closed surface (`AC-RP-3`) and fails until it is listed.
- **`tests/test_decomposition.py`**: `_NEW_MODULES` gains `"delta"`, putting
  the new module under the existing stdlib-only and import-boundary guards.
- **`tests/test_delta.py`** (new): the pure unit tests for `build_delta` and
  `DeltaEntry`. **None of these tests exist yet** — see `tasks.md`.
- **`tests/test_graft.py`**: the CLI-level `delta` tests, alongside the
  existing `detect --diff` and `waivers` CLI tests. **None exist yet.**
- Docs: `README.md`'s CLI verb list and a usage example;
  `skills/planlint-spec-governance/references/exit-codes.md` gains `delta`
  beside the existing "one exit-1 case that is not a finding" paragraph, since
  `delta`'s exit 1 is that same kind of case; `CHANGELOG.md`;
  `docs/differentiation-roadmap.md`'s CP-5 section, to record that `--since`
  was rejected and what shipped instead.

## Non-Goals

- **No `--since <ref>`, and no git.** Rejected on the record in `DEC-DL-001`,
  not deferred. `delta` adds no `subprocess` call site anywhere:
  `tests/test_decomposition.py::test_only_detect_imports_subprocess` keeps
  passing untouched, and `detect._current_sha` remains the only one.
- **No new rule.** Nothing here is a spec-quality finding, so
  `openspec_graph/rules.py`'s `RULES` tuple and `README.md`'s rules table are
  unchanged, and no golden rule hash is re-pinned. A `DeltaEntry` is
  deliberately not a `rules.Finding`: it must never appear in `rules --json`,
  `validate`'s `findings` array or `blocking` count, or the graph's
  `broken_links` (`DEC-DL-003`).
- **No re-linting.** A citation that was *already* broken in the baseline is
  not `delta`'s business — G004 already fails a spec citing a make target the
  repo does not have, and G005 already reports an undeclared `INV-n`. What
  `delta` adds is **attribution**: this citation is stale *because the
  machinery changed since the baseline*. Reporting the already-broken case
  would make `delta` a rename of `validate` with a worse exit-code story
  (`DEC-DL-002`, `R-DL-2`, `AC-DL-6`).
- **No `--change` scoping.** `delta`'s question is about the whole tree by
  construction — "which specs still point at the old world" — and a scoped
  answer would silently under-report. `--change` can be added later without
  changing the entry shape if a real need appears.
- **No `--fail-on`.** `delta` has no severities to threshold on; a stale
  citation either exists or does not. Exit 1 *is* the report, the same posture
  `detect --diff` already takes.
- **No baseline authoring.** `delta` does not write, refresh, or discover a
  baseline card. The operator saves one with `detect --format json` and passes
  its path, exactly as `detect --diff` requires today.

## Affected Capabilities

- `delta-lint`
