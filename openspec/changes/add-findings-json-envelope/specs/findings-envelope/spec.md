# Spec: Findings Envelope

> **Change:** `add-findings-json-envelope`
> **Version:** 1.0.0-draft
> **Authors:** maintainer · reviewer
> **Status:** APPROVED

---

## Problem Statement

`cli.cmd_validate`'s `--json` branch (`cli.py:307-319`) emits
`{target, specs_checked, findings, blocking}`. The payload carries no schema
version, so a consumer has no way to detect a shape change other than
crashing on it; no tool version, so an artifact cannot be attributed to the
build that produced it; and each `findings[].path` is
`rule_types.Finding.as_dict()`'s `str(self.path)` — an absolute,
native-separator path valid only on the machine that produced it.

**Evidence:** `.github/workflows/ci.yml:62-72` writes the output to
`spec-findings.json` and uploads it with `actions/upload-artifact@v4`. The
adopter-facing `templates/spec-gate.yml:44-52` does the same, as does its
byte-identical twin `skills/planlint-spec-governance/assets/spec-gate.yml`,
which ships inside the distributed Agent Skill. Every path in an uploaded
artifact points into `/home/runner/work/...`, a directory the reader of the
artifact does not have. The same skill's `SKILL.md:38-40` recommends
`validate --json` for structured output in the same sentence that it praises
`detect --format json` as "a portable, schema-versioned dialect card" and
warns that `detect --json` is "a legacy shape carrying machine-specific
absolute paths" — an accurate description of `validate --json` itself.

Two further defects sit in the same code path. `validate --json` emits
findings in raw evaluation order while the plain-text branch sorts them
through `_sort_key` (`cli.py:321-334`), so the two renderings of one run
disagree; and `detect --json` (`cli.py:506-507`, self-described as "legacy")
selects `StackProfile.as_dict()`, whose `root`/`openspec_root`/`speckit_root`
fields are absolute paths.

`CHANGELOG.md`'s `[0.2.0]` header records that `v0.1.0` "was never published
to a package index" and that publication of `v0.2.0` happens when its tag is
pushed. Every correction here is free today and a breaking change for real
adopters after that tag.

---

## Requirements

- R-FE-1: `validate --json`'s payload MUST carry a top-level
  `schema_version` (integer) and `tool_version` (string) in addition to
  `target`, `specs_checked`, `findings`, and `blocking`. The four existing
  keys MUST keep their exact spellings and meanings; this change MUST NOT
  rename or remove any of them.
- R-FE-2: Every `findings[].path` for a finding whose path lies under
  `target` MUST be a forward-slash, `target`-relative string computed by
  `detect.to_posix_relative` — never an absolute path and never a
  native-separator one.
- R-FE-3: The top-level `target` field MUST remain an absolute path string
  rendered exactly as it is today (`str(prof.root)`). It is the base every
  `findings[].path` resolves against; relativizing it would make the payload
  no longer self-describing.
- R-FE-4: `Finding.as_dict()` MUST accept an optional
  `root: Path | None = None`. With `root` omitted or `None`, its output MUST
  be byte-identical to the pre-change output for every field, so no caller
  other than `cmd_validate` changes behavior.
- R-FE-5: A `Finding` whose `path` is not under `root` MUST still appear in
  `findings`, with `path` rendered as `path.as_posix()`. It MUST NOT be
  dropped from the array, MUST NOT be rendered as `None`, and `as_dict()`
  MUST NOT raise. A `Finding` whose `path` is `None` MUST continue to
  serialize as JSON `null`, unchanged.
- R-FE-6: The `findings` array MUST be ordered by the same key the
  plain-text branch orders by (posix-relative path, then rule id). One
  implementation of that key MUST serve both branches; the two MUST NOT
  carry independent copies.
- R-FE-7: The schema version MUST be declared once as a named module-level
  constant (`FINDINGS_SCHEMA_VERSION`) and MUST NOT appear as an integer
  literal at the emitting call site.
- R-FE-8: `tool_version` MUST be resolved through the same code path
  `--version` uses, and the underlying distribution lookup MUST be
  **memoized** (`functools.cache` on `cli._package_version`) so that it runs
  at most once per CLI invocation no matter how many times it is called. No
  second `importlib.metadata` lookup or hardcoded version string may be
  introduced. The once-per-run property MUST be a property of the function,
  not of call-site discipline: two independent callers already exist.
- R-FE-9: `detect --json` MUST print exactly one deprecation line to
  **stderr**, naming `--format json` as the portable replacement. Its
  **stdout** MUST remain byte-identical to today's.
- R-FE-10: `tests/test_decomposition.py::_run_cli()` MUST normalize the
  `tool_version` value before hashing, the way it already normalizes the
  root path to `<ROOT>`, so that a version bump alone can never require
  `_EXPECTED_HASHES["validate"]` to be re-pinned again.
- C-FE-1: This change MUST NOT alter the shape of `graph --format json`,
  `waivers --format json`, `rules --json`, `detect --format json`, or
  `ledger.LedgerEntry.as_dict()`, and MUST NOT change
  `_EXPECTED_HASHES["graph"]` or `_EXPECTED_HASHES["rules"]`.
- C-FE-2: This change MUST NOT remove the `detect --json` flag, change its
  exit code, or change the `StackProfile.as_dict()` shape it prints.
- C-FE-3: `StackProfile.root` and `StackProfile.openspec_root` MUST remain
  absolute, platform-native paths. `DEC-PS-002`'s reasoning is overturned
  only for `Finding.as_dict()`'s `path` field, not for these.
- C-FE-4: `validate`'s plain-text output, every exit code, and
  `json.dumps`'s `indent=2`/`ensure_ascii` behavior MUST be unchanged.

---

## Decisions

- **DEC-FE-001 (supersedes `DEC-PS-002`, in part):**
  `Finding.as_dict()`'s `path` becomes `target`-relative and posix **when a
  `root` is supplied**, and stays absolute and native-separator when it is
  not. `fix-windows-path-separator-leak`'s `DEC-PS-002` deliberately excluded
  this field, on two arguments. This decision defeats the **first** and
  leaves the **second** standing.
  The first argument was that absolute self-referential fields are "never
  compared across two checkouts of the same repo: two developers' or two CI
  runners' absolute paths to 'this repo' never match to begin with, so
  posix-normalizing them buys no portability." That rests on a factual
  premise — that the value never leaves the machine that produced it — which
  `.github/workflows/ci.yml` and the adopter-facing `templates/spec-gate.yml`
  falsify directly: both write the payload to `spec-findings.json` and hand
  it to `actions/upload-artifact@v4`, whose entire purpose is to make it
  readable off the runner. The consumer of that artifact is not asking "does
  this string equal my own path" (it never will, and `DEC-PS-002` is right
  about that); it is asking "which file in the repository", and a
  runner-absolute path cannot answer that at all.
  The second argument was that because `as_dict()`'s `path` is "*always*
  absolute … there is no normally-relative case for its separator to be
  consistent with." That argument is **not** overturned, and an earlier draft
  of this decision overstated the matter by claiming the field is "normally
  relative" now. It is not. `as_dict()`'s default is still absolute and
  native-separator, deliberately (`R-FE-4`, `DEC-FE-005`), and that default
  is what every caller outside this repository keeps getting. Inside the
  package there is exactly one call site — `cli.cmd_validate`'s `--json`
  branch, `[f.as_dict(prof.root) for f in ordered]` — and it always passes a
  root. So the honest statement is narrower than "the field changed shape":
  one caller opts into a portable rendering, the method's own default
  preserves the old one byte for byte, and the outside-root fallback is posix
  only within the branch that already relativizes. `DEC-PS-002`'s
  consistency-within-the-method reasoning is what the opt-in shape exists to
  respect, not something this change had to break.
  Two consequences are recorded rather than left to be rediscovered. First,
  this supersession is scoped to `Finding.as_dict()` alone;
  `StackProfile.root`/`openspec_root` and `validate --json`'s `target` stay
  absolute (`C-FE-3`, `DEC-FE-002`). Second, `DEC-PS-005`'s justification for
  `tests/test_decomposition.py::_run_cli()`'s *second*, JSON-escaped `<ROOT>`
  replacement pass now rests on a single field. That pass exists because
  `json.dumps` doubles each backslash in an absolute Windows path, so the raw
  substitution never matched; before this change both `target` and every
  `findings[].path` were such fields, and afterwards only `target` is. The
  pass is still required and still correct — one field is enough to need it —
  but its blast radius is now one key, and a future change that relativizes
  `target` would retire it entirely.
  `tests/test_enterprise.py::test_finding_as_dict_path_field_stays_absolute_and_native`
  is therefore **kept**, not replaced: its subject — the unchanged default —
  is exactly what survives. A sibling test asserts the rooted rendering
  beside it, so both halves of the contract are pinned where the old one was.
- **DEC-FE-002:** `target` stays absolute. It is not an oversight carried
  forward from `DEC-PS-002` but a load-bearing choice: with every
  `findings[].path` now relative, `target` is the only field that says
  *what they are relative to*. Dropping or relativizing it would leave a
  consumer unable to reconstruct a real path even when it is running on the
  same machine, and would break the existing `<ROOT>` normalization
  `tests/test_decomposition.py::_run_cli()` depends on. A consumer that
  wants a portable payload strips one known field; a consumer that wants a
  local path joins it. Both are served.
- **DEC-FE-003:** existing key spellings are preserved verbatim, including
  `specs_checked` and `blocking`. Renaming them would be a second,
  independent break landing in the same release; a consumer would then have
  to migrate two unrelated things at `schema_version` 1, and the version
  number would carry no information about which of them broke it. The
  envelope is therefore purely additive at the key level, with exactly one
  value-shape change (`findings[].path`), which is what the version number
  exists to announce.
- **DEC-FE-004:** `FINDINGS_SCHEMA_VERSION` lives in `rule_types.py`, beside
  the `Finding` it versions, and is re-exported through `rules.py`'s facade
  `__all__`. This mirrors both existing precedents — `dialect_card.py`
  declares `SCHEMA_VERSION` in the module that owns the card's shape, and
  `witness.py` declares `WITNESS_SCHEMA_VERSION` in the module that owns the
  witness's — rather than inventing a third home. It is deliberately *not*
  placed in `cli.py`: the version describes the serialization of `Finding`,
  which `rule_types.py` owns, and a constant in `cli.py` could not be
  imported by anything else without inverting the layer order that
  `tests/test_decomposition.py::test_import_boundary_discipline` enforces.
  The facade re-export follows `R-DG-1`, so `cli.py` reaches it as
  `rules.FINDINGS_SCHEMA_VERSION` like every other rule-layer name it uses,
  instead of adding a direct `rule_types` import.
- **DEC-FE-005:** `as_dict()` takes an optional `root` defaulting to `None`
  rather than a required parameter or a separate `as_portable_dict()`
  method. A required parameter would be a breaking signature change for a
  public dataclass method with no way to stage it; a second method would
  leave two serializers to drift apart, which is the exact failure mode
  `to_posix_relative` was created to end (`DEC-PS-003`). The default
  preserves today's behavior byte-for-byte, so the one caller that wants
  portability opts in and every other call site is provably unaffected.
- **DEC-FE-006:** `_version_string()` is split into `_package_version() ->
  str` (bare version) and `_version_string()` (`f"%(prog)s
  {_package_version()}"`). `_version_string()` cannot be reused as-is:
  it returns an argparse format template containing the literal
  `%(prog)s`, which argparse expands at print time — putting that string in
  a JSON field would emit `"%(prog)s 0.2.0"`. The split keeps the argparse
  token at the argparse boundary and leaves exactly one distribution-lookup
  implementation. The helper is named `_package_version`, and it carries
  `@functools.cache`.
  The cache is load-bearing, not an optimization, and the reason is a
  correction to this decision as first written. It claimed the lookup "is
  called once per invocation, so it cannot print twice." That was **false**
  as built and was measured to be false: `build_parser()` passes
  `version=_version_string()` to argparse, which evaluates the call on
  **every** invocation of **every** verb regardless of whether `--version`
  was passed, and `cmd_validate` then calls `_package_version()` again for
  the envelope's `tool_version` — two lookups in one `validate --json` run,
  and therefore two copies of the multi-distribution `WARNING:` line in
  exactly the stale-install case that warning exists to report. Nothing about
  the call sites made the claim true; memoization is what makes it true, and
  `R-FE-8` states the memoization rather than the discipline.
  `tests/test_findings_envelope.py::test_package_version_is_the_single_lookup_site`
  measures the property directly — it runs `validate --json` in a subprocess
  with two distributions patched in and asserts the ambiguity warning appears
  exactly once — so what used to be an assertion in prose is now pinned.
  Recorded this
  way deliberately: "we were careful" is not a mechanism, and a future caller
  adding a third `_package_version()` call would have silently reintroduced
  the duplicate warning under the old framing.
  Two consequences follow. `_package_version()` now emits that `WARNING:`
  line on `validate --json` where previously it fired only on `--version` —
  correct, because the `tool_version` recorded in a CI artifact is exactly
  the value the warning says may be wrong, and harmless to the payload,
  because it goes to stderr while the JSON goes to stdout. And a cached
  lookup is process-global state that in-process tests can inherit from each
  other, so `tests/conftest.py` clears it around every test
  (`cli._package_version.cache_clear()` before and after); without that, a
  test monkeypatching `importlib.metadata` would pass or fail on execution
  order.
- **DEC-FE-007:** the sort-order fix is folded into this change rather than
  filed separately. It is not scope creep: this change is already re-pinning
  `_EXPECTED_HASHES["validate"]` and already rewriting the same four lines
  of `cmd_validate`. Landing the ordering fix later would mean a second
  re-pin of the same hash and a second `schema_version`-visible change to
  the same array for consumers who assumed evaluation order was stable.
  `_sort_key` moves to module level so the JSON and text branches provably
  call one function — a closure defined inside `cmd_validate` after the
  `--json` branch has already returned cannot be shared, and copying it
  would recreate the duplication `DEC-PS-004` was fixed for.
- **DEC-FE-008:** the golden-hash harness normalizes `tool_version` instead
  of the test asserting the version. `_run_cli()` already normalizes the
  root path to `<ROOT>` for exactly this reason — a value that legitimately
  varies per run must not be part of a pinned hash. Without this,
  `_EXPECTED_HASHES["validate"]` would need re-pinning on every release,
  turning a drift guard into a release chore and training maintainers to
  re-pin it reflexively — which is how a real drift gets waved through. The
  hash is re-pinned exactly once, in this change, for the envelope itself
  (its own comment block already records three prior re-pins and their
  reasons; this adds a fourth with the same discipline).
- **DEC-FE-009:** `detect --json` is deprecated by notice, not removed, and
  the notice goes to stderr. Removal before the flag has ever shipped in a
  published release would be defensible, but the flag is named in
  `tests/test_enterprise.py::test_cli_verbs_backward_compatible`'s
  parametrization as part of the v0.1.0 surface this project promised to
  keep, and `AC-EH-7` exists to hold that promise. A stderr line changes
  nothing for a consumer that redirects stdout to a file — which is the only
  documented use — while a stdout line would corrupt the very JSON the flag
  exists to produce. Removal target is stated as `1.0` in `CHANGELOG.md`, the
  same boundary `templates/spec-gate.yml`'s `"planlint>=0.2.0,<1"` pin
  already treats as the breaking-change line.
- **DEC-FE-010:** `FINDINGS_SCHEMA_VERSION` starts at `1`, not at `2` and
  not at the package version. `1` matches both existing constants
  (`dialect_card.SCHEMA_VERSION = 1`, `witness.WITNESS_SCHEMA_VERSION = 1`)
  and states the honest fact that this is the first *versioned* shape — the
  unversioned predecessor is not a "version 0" a consumer could ever have
  read, because it carried no field to read it from. Coupling the schema
  version to the package version would force a schema bump on every
  unrelated release, which is what `tool_version` is separately for.

---

## Acceptance Criteria

- [x] **AC-FE-1:** `validate --json` emits exactly the keys
  `schema_version`, `tool_version`, `target`, `specs_checked`, `findings`,
  `blocking`; `schema_version` equals `rules.FINDINGS_SCHEMA_VERSION` and is
  an `int`, `tool_version` equals the version `--version` reports, and
  `target` is an absolute path. (R-FE-1, R-FE-3, R-FE-7, R-FE-8, DEC-FE-002,
  DEC-FE-004, DEC-FE-010)
  _Verified by:_ `pytest -k "test_existing_keys_keep_their_spelling or test_envelope_carries_a_schema_version or test_envelope_carries_the_tool_version or test_target_stays_absolute"` · stage: `make test`

- [x] **AC-FE-2:** Every `findings[].path` in a `validate --json` run over a
  fixture repo with findings in two different spec files is a forward-slash
  string relative to `target` — no leading separator, no drive letter, no
  backslash, no copy of the checkout path — and `target / path` resolves to
  the file the finding is about. The fixture is asserted non-empty first, so
  the criterion cannot pass vacuously. (R-FE-2, DEC-FE-001)
  _Verified by:_ `pytest -k test_every_finding_path_is_relative_and_posix` · stage: `make test`

- [x] **AC-FE-3:** The same logical repository, materialized at two
  different checkout paths of different lengths, produces byte-identical
  `validate --json` output once the `target` field alone is normalized —
  the property the uploaded CI artifact actually needs. (R-FE-2, R-FE-3,
  R-FE-6, DEC-FE-001)
  _Verified by:_ `pytest -k test_two_checkout_paths_produce_identical_json` · stage: `make test`

- [x] **AC-FE-4:** For one run over a fixture repo producing findings in two
  spec files, the sequence of `(path, rule)` pairs in `findings` is sorted
  and equals the sequence the plain-text branch prints, in order; and the
  `blocking` count still matches the findings after that reordering.
  (R-FE-6, DEC-FE-007)
  _Verified by:_ `pytest -k "test_findings_are_sorted_like_the_text_renderer or test_blocking_count_still_matches_the_findings"` · stage: `make test`

- [x] **AC-FE-5 (non-success):** `Finding.as_dict(root)` for a finding whose
  path is genuinely outside `root` still returns an entry, with `path`
  equal to `path.as_posix()` — never `None`, never omitted, never raising.
  This state is unreachable through any CLI path, because every
  `Finding(...)` construction site derives its path from a resolved
  `openspec_root` under `target`; the test therefore constructs a `Finding`
  directly rather than driving the CLI, so the criterion is exercised for
  real instead of passing vacuously on an empty set. A `Finding` with
  `path=None` still serializes as JSON `null`, and a clean tree still
  reports an empty `findings` list rather than a manufactured one. (R-FE-5)
  _Verified by:_ `pytest -k "test_a_finding_outside_the_target_is_emitted_not_dropped or test_a_finding_with_no_path_stays_none or test_clean_repo_still_reports_an_empty_findings_list"` · stage: `make test`

- [x] **AC-FE-6 (non-success):** `Finding.as_dict()` called with no argument
  returns exactly the pre-change dict — `path` is `str(self.path)`,
  native-separator and absolute — so no caller other than `cmd_validate`
  changes behavior, and `DEC-PS-002`'s second argument stays intact.
  (R-FE-4, DEC-FE-005)
  _Verified by:_ `pytest -k "test_as_dict_without_a_root_is_unchanged or test_finding_as_dict_path_field_stays_absolute_and_native"` · stage: `make test`

- [x] **AC-FE-7 (non-success):** `detect --json`'s **stdout** still parses to
  the same `StackProfile.as_dict()` payload with no deprecation text in it,
  its exit code is unchanged, and its **stderr** carries exactly one line,
  which names `--format json`; `detect --format json` does not inherit the
  warning. (R-FE-9, C-FE-2, DEC-FE-009)
  _Verified by:_ `pytest -k "test_detect_json_stdout_is_unchanged or test_detect_json_warns_that_it_is_deprecated or test_detect_format_json_is_not_deprecated"` · stage: `make test`

- [x] **AC-FE-8:** `tests/test_decomposition.py::_run_cli()` normalizes the
  `tool_version` value before hashing, so `_EXPECTED_HASHES["validate"]`
  needs no re-pin for a version change; the hash it pins is the one this
  change re-pinned once, for the envelope itself. (R-FE-10, DEC-FE-008)
  _Verified by:_ `pytest -k "test_output_byte_identical or test_run_cli_normalizes_tool_version"` · stage: `make test`

- [x] **AC-FE-9 (non-success):** `_EXPECTED_HASHES["graph"]` and
  `_EXPECTED_HASHES["rules"]` are unchanged, and every other JSON surface
  emits its pre-change shape: `graph --format json` and `rules --json` by
  golden hash, `waivers --format json` by its own field assertions,
  `detect --format json` by its dialect-card assertions, and
  `ledger.LedgerEntry.as_dict()` directly. This change touches one output
  only. (C-FE-1)
  _Verified by:_ `pytest -k "test_output_byte_identical or test_ledger_entry_as_dict_shape or test_cli_waivers_json_lists_reason_file_line_and_change or test_detect_format_json_emits_a_dialect_card_with_schema_version"` · stage: `make test`

- [x] **AC-FE-10:** `_package_version()` is the only distribution-lookup
  implementation in the package, it is memoized so one CLI run performs one
  lookup and prints at most one ambiguous-environment `WARNING:` however
  many callers ask, the envelope's `tool_version` is the value that lookup
  returns, and `--version`'s printed output is unchanged. (R-FE-8,
  DEC-FE-006)
  _Verified by:_ `pytest -k "test_package_version_is_the_single_lookup_site or test_version_flag_output_is_unchanged or test_cli_version_flag_reports_the_package_version"` · stage: `make test`

- [x] **AC-FE-11:** `SKILL.md`'s structured-output paragraph and
  `CHANGELOG.md`'s `[Unreleased]` section describe the new envelope, the
  path change as a deliberate partial supersession of `DEC-PS-002`, and the
  `detect --json` removal target of `1.0`. No doc still describes
  `validate --json` as carrying absolute finding paths. (R-FE-1, R-FE-9,
  DEC-FE-009)
  _Verified by:_ manual review · stage: `make docs-check`

- [x] **AC-FE-12 (non-success):** nothing outside the one output changed
  shape. `StackProfile.root` is still an absolute, platform-native path in
  `detect --json`'s payload — `DEC-PS-002` is overturned for
  `Finding.as_dict()`'s `path` only. `validate`'s plain-text rendering is
  still parseable line-for-line into the same `(path, rule)` pairs the JSON
  reports, its exit codes are unchanged across every verb, and the pinned
  golden hashes prove `json.dumps`'s `indent=2`/`ensure_ascii` behavior is
  byte-identical. (C-FE-3, C-FE-4)
  _Verified by:_ `pytest -k "test_detect_json_stdout_is_unchanged or test_findings_are_sorted_like_the_text_renderer or test_output_byte_identical or test_cli_verbs_backward_compatible"` · stage: `make test`

---

## Invariants Touched

None — this repo declares no invariant source; no `INV-n` is cited by this
spec.

## Validation Matrix

| Stage | Make Target | Pass Criteria |
|---|---|---|
| Focused | `make test` | AC-FE-1..10, AC-FE-12 |
| Core | `make ci` | AC-FE-1..10 and AC-FE-12, plus lint and this repo's own `planlint validate` |
| Docs | `make docs-check` | AC-FE-11 (manual review; no automated content check covers SKILL.md prose) |
| Full | `make pre-pr` | full regression, lint, typecheck, security, docs, no-hardcoded-thresholds |
