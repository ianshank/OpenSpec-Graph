# Change: Fix Adopter-Artifact Drift

## Why

`rename-cli-and-positioning` (PR #5) renamed the primary CLI from `specgraph`
to `planlint`, but its own touch map did not include three adopter-facing
artifacts, so they drifted. Ironically, this is exactly the class of
doc/reality drift `planlint` exists to catch in other people's repos — this
change fixes it in its own.

**Evidence:** `templates/spec-gate.yml` — the copy-paste CI template meant for
adopters' own repos — wraps every `run:` shell command in literal backticks
(present since the first commit, `cdc94ca`, confirmed via `git log --follow`;
this predates the rename entirely). GitHub Actions' bash treats backticks as
command substitution rather than literally running the command, and on one
line the substitution silently eats the `--fail-on ERROR` flag. The same file
installs from `pip install openspec-graph`, a PyPI name that returns 404 (the
package is not yet published). `Dockerfile` and `.pre-commit-config.yaml`
still invoke the deprecated `specgraph` alias in their executable lines.
Separately, `README.md` and `docs/differentiation-roadmap.md` both cite a
`docs/specs/SPEC_TEMPLATE.md` file that does not exist anywhere in the
repository, `docs/architecture/c4.md`'s module map predates the
`decompose-god-files` refactor (9 real modules missing), `CHANGELOG.md`'s
`[Unreleased]` section has no entries for the two most recent merged PRs, and
`LICENSE` carries an unfilled Apache-2.0 copyright placeholder.

## What Changes

- `templates/spec-gate.yml`: remove the literal backticks from all `run:`
  steps, fix the install step to a source that resolves, `specgraph` →
  `planlint` throughout.
- `Dockerfile`: all four stale `specgraph` references → `planlint`.
- `.pre-commit-config.yaml`: the `specgraph-validate` hook's `entry:` line →
  `planlint`.
- `openspec_graph/detect.py` docstring and `.github/workflows/ci.yml` comment:
  fix two smaller stale-name mentions found while auditing the rename.
- `README.md` and `docs/differentiation-roadmap.md`: reword the dangling
  `docs/specs/SPEC_TEMPLATE.md` references in place to cite the two existing,
  live demonstrations of the G002 non-success-criterion pattern
  (`tests/fixtures/good_harness.md` and `good_upstream.md`) instead of a
  nonexistent file.
- `docs/architecture/c4.md`: rewrite the module map to show the facade
  pattern the `decompose-god-files` refactor actually produced.
- `CHANGELOG.md`: add `[Unreleased]` entries for PR #5
  (`rename-cli-and-positioning`) and PR #4 (`decompose-god-files`).
- `LICENSE`: fill the copyright placeholder (`2026`, `Ian Shank` — see
  Non-Goals; this default should be confirmed, not treated as final).

## Non-Goals

- No new CI-gate script (e.g. a permanent `tools/check_adopter_artifacts.py`)
  to guard against this drift recurring. Per `docs/next-steps.md`'s own
  standard, adding process before its value is proven is over-engineering;
  this is a one-time sweep, not a continuously-regenerating risk the way a
  hard-coded threshold is. If protection is wanted later, the cheapest form
  is a single test, not a new tool.
- No new `docs/specs/SPEC_TEMPLATE.md` document. Authoring a real,
  dialect-covering spec template is separate content-design work with its
  own review surface; this change rewords the dangling reference instead.
- No rename of the identifiers `rename-cli-and-positioning` explicitly kept
  as `specgraph`: the waiver comment syntax (`<!-- specgraph:allow ... -->`),
  the config file (`openspec/specgraph.json`), the `[tool.specgraph]`
  pyproject section, and the pre-commit hook `id:`/`name:` fields (renaming
  hook ids is a minor breaking change for anyone who has them pinned locally,
  for little benefit).
- The copyright holder name (`Ian Shank`) is a proposed default based on git
  history (majority of substantive early commits; matches the account's
  on-record email), not a unilateral final legal decision — flagged for
  confirmation.
- No git tag action: `v0.1.0` already exists on the GitHub remote
  (`git ls-remote --tags origin` confirms it at `cdc94ca`); the CHANGELOG's
  release link is already correct.

## Affected Capabilities

- `adopter-artifacts`
