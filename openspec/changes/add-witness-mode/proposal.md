# Change: Add Witness Mode (CP-WM / roadmap `CP-7`)

## Why

`planlint` checks that a spec's `_Verified by:_` line *cites* a real make
target (H001, and the `MAKE_REF` regex generally) — but never checks that the
target was actually *run*, let alone that it passed. A spec can cite
`` `make test` `` and pass every existing lint check while the tests it
references have never once executed. Witness mode closes that gap: CI records
a small "witness" proving a stage actually ran (exit code, coverage, commit
sha), and `validate --require-witness` fails unless every criterion's cited
stage has a matching, fresh, passing witness.

This capability is committed to the repo's own roadmap as `docs/differentiation-roadmap.md`'s
`CP-7` section, quoted there as *"the line competitors can't cross."* That
sketch is real product intent but not literal architecture — it has four
concrete problems this design fixes rather than just implements: its own
`witness record --target test` flag collides with the *global* `--target`
(repo path) every other verb already uses identically; "H001 verifies witness
when flag set" is architecturally impossible as stated, since `Rule.check()`
has no access to CLI flags and no existing rule conditionally activates on a
runtime one; "signed (hash-chained)" names no key-management story anywhere;
and it says nothing about `--change` interaction, `AC-GR-4`/graph parity, or
rule-family placement.

This proposal went through two adversarial review rounds before
implementation — an initial design pass (3 Explore agents + 1 Plan agent),
then a dedicated adversarial peer review (2 independent reviewers) that found
a real HIGH-severity bug introduced during the first draft itself: a
short-commit-sha comparison that would have silently defeated freshness
checking for any CI script using abbreviated shas (`git rev-parse --short
HEAD`, `${GITHUB_SHA:0:7}` — both ordinary patterns). That review also found
the pre-existing `Criterion.verified_by` waiver-comment leak (open, unfixed,
since before this change) is wider for the upstream dialect than the harness
one — exactly the dialect this design is proudest of supporting — which
would have let W001/W002 ship with a real, gate-defeating hole in the one
dialect most exercised by them.

## What Changes

- **New rules `W001`/`W002`** (both ERROR, `dialects=("*",)`): `W001` — a
  spec's cited stage has no fresh, exit-0 witness. `W002` — a witness matching
  a cited stage records coverage below the detected floor. Both evaluated
  only when `--require-witness` is passed to `validate`; default `validate`
  behavior is unchanged (roadmap's own Cutline).
- **New `openspec_graph/witness.py`**: `Witness` schema (content-addressed
  JSON under `.planlint/witnesses/`, atomic write via temp-file + rename),
  `load_witnesses()` (fails closed on any unreadable/malformed/hash-mismatched/
  wrong-schema-version/non-finite-coverage file — never raises, never treats
  a bad file as a pass), `matching_witnesses()`.
- **New `openspec_graph/rules_witness.py`**: `W001`/`W002` checks, with
  staged, distinct diagnostic messages (missing vs. stale-commit vs.
  failing-run) rather than one generic "no witness" message for every cause.
- **New `planlint witness` verb**: `--stage`, `--exit`, `--coverage`
  (optional), `--sha` (required, full 40-character hex — never abbreviated,
  never auto-derived from git). Records one witness per invocation.
- **`detect.py` gains its only new subprocess call site**: `_current_sha()`
  (`git rev-parse HEAD`, timeout-guarded, every failure folds to `None`),
  computed lazily — only when at least one witness already exists — so the
  existing 300+-test suite's wall-clock cost is unaffected.
- **`rules.evaluate()` gains an optional `rule_set` parameter**
  (`Sequence[Rule] = RULES`), single-sourcing both the `--require-witness`
  gate and `graph.py`'s exclusion of witness findings from `broken_links`
  through one `NON_WITNESS_RULES` constant, rather than two independently
  maintained filters.
- **Prerequisite fix, folded into this change**: `parse_harness.py`/
  `parse_upstream.py` build each `Criterion.verified_by` from raw,
  waiver-comment-unstripped text, unlike the already-fixed spec-wide
  `make_refs`/`invariant_refs`/`adr_refs` fields. Fixed as this change's own
  first commit, before any witness-consuming rule exists.

## Non-Goals

- **No cryptographic signing, CI-identity binding, or key management.** The
  roadmap's "signed" language never named a key-management story anywhere;
  content-addressing delivers exactly one real guarantee (tamper/corruption
  detection), not authorship, and this change is honest about the
  difference rather than quietly under-delivering on "signed."
- **No hash-chaining, append-only log, or `HEAD`-pointer file.** `.planlint/
  witnesses/` is ephemeral and gitignored, per-checkout — there is no
  persistent history to chain, so chaining would solve a problem this data
  model doesn't have.
- **No independent re-derivation of coverage from the target repo's own
  coverage report.** `--coverage` is trusted as reported, like `--exit` and
  `--sha`. This leaves one real, explicitly named gap: a plausible-looking
  but wrong-unit coverage number (e.g. a raw line count that happens to land
  in `[0,100]`) can't be caught by range-checking alone — documented, not
  hidden.
- **No sha-reachability check (`git cat-file -e`).** A wrong or typo'd sha
  already fails closed via the exact-match comparison with no harm done;
  adding a reachability check would need a second subprocess call site, in
  tension with this change's own single-call-site guard.
- **No `witness verify`/`witness list` sub-verbs.** `witness` is a single,
  flat action; `validate --require-witness` is the only v1 consumer of
  "verify" logic. No nested sub-parser — every existing verb is a
  single-level leaf.
- **No graph/Mermaid representation of witnesses, ever, and no
  `--require-witness` flag on `graph`.** Witness-checking is an operational
  CI-proof concern, not a structural spec-dependency edge; W001/W002 are
  excluded from `graph`'s `broken_links` entirely — a stronger exclusion
  than the existing H/U-family precedent (whose findings still count toward
  `broken_links` even without a dedicated node/edge type).
- **No smarter "which citation is the real one" heuristic** for a scenario
  citing multiple stages (e.g. a GWT block mentioning both `` `make build` ``
  and `` `make test` ``). Every backtick-fenced citation requires its own
  witness — strict, but consistent with citation already being opt-in via
  backtick-fencing. This project already paid for exactly one fragile
  "guess which mention is the real one" heuristic this session (the ADR
  first-mention-vs-heading fix) and shouldn't repeat the pattern here.
- **No redesign of `evaluate(rule_set=...)` in anticipation of
  `add-rule-pack-plugins`'s own, separate, not-yet-re-grounded plan to reuse
  the same parameter name for plugin filtering.** Flagged as a known future
  integration point for that change's own re-grounding pass, not resolved
  here.
- **No new CLI verb beyond the single `witness` verb** — the closed verb set
  (`tests/test_cli_surface.py::ALLOWED_VERBS`) grows by exactly one,
  deliberately, not by accident.

## Affected Capabilities

- `witness-mode`
