# Change: Add SARIF Output and a Composite Action (CP-6)

## Why

Every finding this tool produces currently ends its life as text in a CI log,
or as a JSON artifact a human has to download and open by hand. Neither one
appears where the organization already looks: the pull request. GitHub code
scanning ingests SARIF and renders each finding inline on the diff — so the
same rule engine, emitting a different projection of the same findings, turns
"a red X and a log to scroll" into "an annotation on line 14 of the spec that
lied." The roadmap's stated goal for this package is time-to-first-red-X
under five minutes on a repository nobody set up in advance.

**Evidence:** `openspec_graph/cli.py::cmd_validate`'s `--json` branch
(`cli.py:417-438`) is the only machine-readable rendering `validate` has, and
both shipped CI recipes treat it as a write-and-forget artifact:
`.github/workflows/ci.yml:62-72` and the adopter-facing
`templates/spec-gate.yml:44-52` each run
`validate --fail-on WARN --json > spec-findings.json || true` and hand the
file to `actions/upload-artifact@v4`. The `|| true` is the tell — the payload
is deliberately non-blocking, which means nothing surfaces it and no reviewer
reads it. `docs/differentiation-roadmap.md`'s `CP-6` section commits this
capability (`AC-SA-1..3` there, sketch only), and its own Risk table already
records the cutline this design must hold: *"SARIF finding loss / GitHub
rejects a finding shape / Map to supported subset; never drop ERRORs."*

Two facts found while grounding the design against the current tree, both of
which change what has to be built:

1. **Every `Finding` reaching `--json` has `line == 0`.** `rules.evaluate()`
   (`rules.py:86-93`) and `rules.evaluate_tree()` (`rules.py:118-139`) are
   the only `Finding(...)` construction sites in the package, and neither
   passes `line=`. SARIF requires `region.startLine >= 1`, so a naive mapping
   would either crash a strict consumer or clamp every finding to line 1 —
   inventing a location that points at the wrong line of a real file. Line
   information is emitted only when it exists.
2. **`tests/test_adopter_urls.py` does not currently discover
   `.github/`.** Its `_adopter_files()` globs `*.md`, `docs/**/*.md`,
   `skills/**/*.md`, `skills/**/*.yml`, `templates/*.yml`, and `Dockerfile`
   (`test_adopter_urls.py:147-155`). The planning pass assumed a composite
   action's pinned install line would be covered by that existing guard. It
   would not be. Widening the corpus is part of this change, not an
   assumption it gets to lean on.

## What Changes

- **`openspec_graph/cli.py`** — `validate` gains
  `--format {text,json,sarif}` (default `text`). `--json` is preserved as an
  exact alias of `--format json`, byte-identical stdout and identical exit
  codes, because two shipped CI templates, `SKILL.md`, and
  `tests/test_enterprise.py::test_cli_verbs_backward_compatible` all pass it.
  `--json` together with `--format sarif` is a usage error (exit 2, stderr,
  nothing on stdout) rather than a silent precedence rule. The SARIF branch
  is fed the *same* `ordered` list the text and JSON branches already build.
- **New `openspec_graph/sarif.py`** — pure, stdlib-only, no I/O, zero
  intra-package import, mirroring `mermaid.py`/`dialect_card.py`. Takes
  already-serialized finding dicts (`Finding.as_dict(root)`) plus
  `rules.rule_table()` and returns a SARIF 2.1.0 log as a plain dict. It
  never evaluates a rule, never touches the filesystem, and never sees a
  `Path`.
- **Severity mapping** — `ERROR` → `"error"`, `WARN` → `"warning"`,
  `INFO` → `"note"`, declared once as a module-level mapping. An `ERROR`
  never maps below `"error"`; an unrecognized severity maps *up*, to
  `"error"`, never down to SARIF's invisible `"none"`.
- **Locations** — `artifactLocation.uri` is the repository-relative POSIX
  path the findings envelope already produces (`Finding.as_dict(root)` via
  `detect.to_posix_relative`), with `uriBaseId: "%SRCROOT%"`.
  `region.startLine` is emitted only for a finding that carries a real line;
  a finding with no path is emitted with an empty `locations` array rather
  than being dropped.
- **`tool.driver.rules`** — built from `rules.rule_table()`, reusing each
  rule's existing `summary` as `shortDescription.text`. No new field is added
  to the `Rule` dataclass: `tests/test_decomposition.py` pins a golden hash
  of `rules --json`, and widening the rule shape would force a re-pin for no
  gain.
- **`.github/actions/planlint/action.yml`** — a composite action that sets up
  Python, installs a pinned `planlint`, runs `detect`, runs
  `validate --format sarif`, and uploads the result with
  `github/codeql-action/upload-sarif`. Its install line uses the same pinned
  range `templates/spec-gate.yml:34` already ships.
- **`tests/test_adopter_urls.py::_adopter_files()`** — corpus widened to
  discover `.github/actions/**/*.yml` and the new root hooks file, so the
  action's install line is actually guarded by the drift test the planning
  pass assumed already covered it.
- **`.pre-commit-hooks.yaml`** at the repository root — the *adopter-facing*
  hook declaration (what another repo's `.pre-commit-config.yaml` points at),
  distinct from this repo's own contributor-facing `.pre-commit-config.yaml`.
  Named by the roadmap's `CP-6` touch map.
- **New `tests/test_sarif.py`**, plus one entry each in
  `tests/test_decomposition.py::_NEW_MODULES` and
  `tests/test_skill_contract.py::READ_ONLY_INVOCATIONS`.

## Non-Goals

- **No GitHub API client, Check Run creation, or token handling inside
  `planlint`.** The roadmap says "SARIF + GitHub Check"; the Check is
  produced by GitHub's own `upload-sarif` action consuming the file. Putting
  an HTTP client in a tool whose entire pitch is "point it at a stranger's
  clone, it only reads" would trade the read-only guarantee for a feature
  GitHub already ships.
- **No `--output-file` / no writing the SARIF anywhere.** stdout only. The
  read-only guarantee (`AC-SD-4`, `AC-DC-3`) is the product, and a
  side-channel report file is exactly the regression
  `tests/test_skill_contract.py::test_read_only_verbs_leave_tree_byte_identical`
  exists to catch. Redirection is the caller's job, as it already is for
  `--json`.
- **No network schema validation.** The suite has no network by policy
  (`tests/test_adopter_urls.py`'s own docstring: "a gate that needs the
  network is a gate that fails on a plane"). SARIF conformance is asserted
  structurally, against the required key set.
- **No SARIF on `graph`, `waivers`, or `rules`.** SARIF describes findings
  with locations and severities; a dependency graph and a rule registry are
  neither. One verb gains one format.
- **No new rules, no new verb, no new rule family.** The registry stays at
  its current 26 rules; `rules --json`'s golden hash is unchanged.
- **No SARIF *ingestion*, merging, or round-tripping.** This emits; it does
  not read SARIF back, diff two logs, or baseline them.
- **No publishing the composite action to the GitHub Marketplace**, and no
  `v1` floating tag. Adopters reference it by the same version range the
  install line pins.
- **No third-party dependency, including a YAML parser.** `sarif.py` is
  stdlib-only under the existing `AC-DG-4` guard, and the new YAML artifacts
  are checked as text — no test in this repository imports `yaml` today.

## Affected Capabilities

- `sarif-output`
