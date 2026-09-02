# Milestones

## Milestone 1 — Portable, opt-in `Finding` serialization

- `openspec_graph/rule_types.py`: `Finding.as_dict()` gains
  `root: Path | None = None`; its `path` field becomes
  `to_posix_relative(self.path, root)` when `self.path` and `root` are both
  present, `str(self.path)` when `root` is `None`, and `None` when
  `self.path` is `None`. `to_posix_relative` is already imported in this
  module for `Finding.render()` — no new import. New module-level
  `FINDINGS_SCHEMA_VERSION = 1` declared beside `Finding`, with a comment
  naming `dialect_card.SCHEMA_VERSION`/`witness.WITNESS_SCHEMA_VERSION` as
  the pattern it mirrors, and added to `__all__`.
- `openspec_graph/rules.py`: import `FINDINGS_SCHEMA_VERSION` from
  `rule_types` and add it to the facade `__all__`, so `cli.py` never needs a
  direct `rule_types` import (R-DG-1).
- `tests/test_enterprise.py`: **keep**
  `test_finding_as_dict_path_field_stays_absolute_and_native` — an earlier
  draft of this plan said to replace it, which was wrong: its subject is the
  *default* rendering, and the default is unchanged (`DEC-FE-001`,
  `DEC-FE-005`). Rewrite only its comment block to say why `DEC-PS-002` was
  superseded in part and what still stands, and add
  `test_finding_as_dict_with_a_root_renders_posix_relative` beside it for the
  other half of the contract.
- `tests/test_findings_envelope.py` (new module): the opt-in half and the
  non-success pair — `test_as_dict_without_a_root_is_unchanged`,
  `test_a_finding_outside_the_target_is_emitted_not_dropped`, and
  `test_a_finding_with_no_path_stays_none`, the last two constructing a
  `Finding` directly since no CLI path can produce an outside-root or
  pathless finding.
- **Gate:** `make test` — AC-FE-5, AC-FE-6.

## Milestone 2 — The envelope, and one shared sort key

- `openspec_graph/cli.py`: extract `_package_version() -> str` from
  `_version_string()` (the distribution lookup, the multi-distribution
  `WARNING:`, and the `__version__` fallback move wholesale);
  `_version_string()` becomes `f"%(prog)s {_package_version()}"` and nothing
  else, keeping the argparse `%(prog)s` token at the argparse boundary.
- `openspec_graph/cli.py`: lift `_sort_key` out of `cmd_validate`'s body to
  a module-level helper over `(finding, root)`, keeping its existing comment
  (the `\`-vs-`/` ordinal argument from `DEC-PS-004`) and its `None`-path
  `"None"` fallback verbatim.
- `openspec_graph/cli.py`: `cmd_validate`'s `--json` branch emits
  `{"schema_version": rules.FINDINGS_SCHEMA_VERSION, "tool_version":
  _package_version(), "target": str(prof.root), "specs_checked": …,
  "findings": [f.as_dict(prof.root) for f in <sorted findings>],
  "blocking": …}` — key order as written, `indent=2` and default
  `ensure_ascii` unchanged, exit codes unchanged. The plain-text branch
  sorts through the same module-level key.
- `openspec_graph/cli.py`: put `@functools.cache` on `_package_version`.
  This is the requirement, not an optimization — argparse resolves the
  version on every parser build and `cmd_validate` needs it again, so without
  the cache the ambiguous-environment `WARNING:` prints twice in one
  `validate --json` run (`R-FE-8`, `DEC-FE-006`).
- `tests/conftest.py`: an autouse fixture calling
  `cli._package_version.cache_clear()` before and after every test. A cached
  lookup is process-global state; without this a test that monkeypatches
  `importlib.metadata` passes or fails on execution order.
- `tests/test_findings_envelope.py`: the envelope's own coverage —
  `test_envelope_carries_a_schema_version`,
  `test_envelope_carries_the_tool_version`,
  `test_existing_keys_keep_their_spelling`, `test_target_stays_absolute`,
  `test_every_finding_path_is_relative_and_posix`,
  `test_two_checkout_paths_produce_identical_json` (two temp roots of
  different lengths, one fixture repo, compare after normalizing `target`
  only), `test_findings_are_sorted_like_the_text_renderer`,
  `test_blocking_count_still_matches_the_findings`, and
  `test_clean_repo_still_reports_an_empty_findings_list`. The fixture writes
  two finding-bearing specs in non-alphabetical creation order, so the
  ordering assertions have something real to sort.
- `tests/test_findings_envelope.py`: `test_version_flag_output_is_unchanged`
  and `test_package_version_is_the_single_lookup_site` — the latter a
  subprocess run with two distributions patched into
  `importlib.metadata`, asserting the ambiguity warning appears exactly once
  in one `validate --json`. A source-level "only one lookup site" check was
  considered and rejected: it would pass on a second *call* to the one
  function, which is the defect that actually occurred.
- Check the existing `validate --json` assertions that already index the
  payload (`tests/test_graph.py:569-571`,
  `tests/test_cli_speckit.py:181-183`, `tests/test_graft.py:2077`) still
  pass unchanged — they read `specs_checked`, which this change preserves
  deliberately (`DEC-FE-003`). Any that need editing indicate an unintended
  key change, not a test to loosen.
- **Gate:** `make test` — AC-FE-1..4, AC-FE-10.

## Milestone 3 — Golden-hash harness, re-pinned once

- `tests/test_decomposition.py`: `_run_cli()` normalizes the `tool_version`
  value to a fixed placeholder before returning, alongside the existing
  `<ROOT>` and JSON-escaped-`<ROOT>` passes; add a comment stating why
  (a per-release value must not be inside a pinned hash — `DEC-FE-008`).
- `tests/test_decomposition.py`: re-pin `_EXPECTED_HASHES["validate"]` once,
  for the envelope; extend the existing re-pin comment block with this
  fourth reason and its cause. Confirm empirically that `["graph"]` and
  `["rules"]` are unchanged — if either moves, this change touched an output
  it declared out of scope (C-FE-1).
- `tests/test_findings_envelope.py`: new
  `test_run_cli_normalizes_tool_version`, proving the normalization actually
  fires rather than silently matching nothing (the failure mode `DEC-PS-005`
  hit on the `<ROOT>` pass). Note while re-pinning that `DEC-PS-005`'s
  JSON-escaped `<ROOT>` pass now protects one field only — `target` — since
  `findings[].path` is no longer absolute; it is still required, but its
  blast radius shrank (`DEC-FE-001`).
- **Gate:** `make test` — AC-FE-8, AC-FE-9.

## Milestone 4 — `detect --json` deprecation notice

- `openspec_graph/cli.py`: `cmd_detect`'s `if args.json:` branch prints one
  line to `sys.stderr` before `json.dumps`, naming `--format json` as the
  portable replacement and `1.0` as the removal release. Stdout, exit code,
  and payload shape untouched.
- `openspec_graph/cli.py`: the `--json` argparse `help=` string on the
  `detect` subparser (`cli.py:506-507`) says "deprecated, removed in 1.0"
  rather than only "legacy".
- `tests/test_findings_envelope.py`: new
  `test_detect_json_stdout_is_unchanged` (stdout still parses to the same
  `StackProfile.as_dict()` payload, with `root` absolute and no deprecation
  text in it — which is also this change's evidence for `C-FE-3`),
  `test_detect_json_warns_that_it_is_deprecated` (exactly one stderr line,
  naming `--format json`), and `test_detect_format_json_is_not_deprecated`
  (the replacement does not inherit the warning). Confirm
  `tests/test_enterprise.py::test_cli_verbs_backward_compatible`'s
  `("detect", "--json")` case still exits 0 or 1.
- **Gate:** `make ci` — AC-FE-7, plus lint and this repo's own
  `planlint validate`.

## Milestone 5 — Docs, changelog, full gate

- `CHANGELOG.md`: `[Unreleased]` entries — the envelope (`schema_version`,
  `tool_version`), `findings[].path` becoming target-relative posix and why
  that supersedes `DEC-PS-002`, the `findings` ordering fix, and the
  `detect --json` deprecation with its `1.0` removal target.
- `skills/planlint-spec-governance/SKILL.md`: the structured-output
  paragraph (`SKILL.md:36-40`) currently recommends `validate --json` in the
  same sentence as the portability warning it fails; reword so
  `validate --json` is described as schema-versioned with target-relative
  paths, and the `detect --json` sentence names the deprecation.
- Re-read `README.md`, `docs/`, and
  `skills/planlint-spec-governance/references/` for any other description of
  `validate --json`'s shape; fix or confirm none exists.
- Confirm `templates/spec-gate.yml` and
  `skills/planlint-spec-governance/assets/spec-gate.yml` are still
  byte-identical to each other (`tests/test_skill_contract.py::test_skill_asset_matches_template`
  enforces this) — neither needs an edit, since the command line is
  unchanged.
- **Gate:** `make pre-pr` — AC-FE-11 and the full enterprise AQA gate green
  end to end.

## Milestone 6 — Close the two constraints no criterion covered

- Add `AC-FE-12`, the non-success criterion for `C-FE-3` and `C-FE-4`. Both
  were declared and then verified by nothing, which this repo's own `H003`
  reports as an orphan requirement on `planlint validate --fail-on WARN` —
  the gate this change package is itself subject to.
- Cite only tests that exist: `test_detect_json_stdout_is_unchanged` for
  `StackProfile.root` staying absolute and native,
  `test_findings_are_sorted_like_the_text_renderer` for the plain-text
  rendering still being parseable line-for-line,
  `test_output_byte_identical` for `json.dumps`'s formatting, and
  `test_cli_verbs_backward_compatible` for the exit codes.
- **Gate:** `planlint --target . validate --fail-on WARN` exits 0 with zero
  findings.
