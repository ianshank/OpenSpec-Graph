# Change: Migrate Licence Metadata to PEP 639

## Why

`pyproject.toml` declared its licence with the `license = { text =
"Apache-2.0" }` table form. setuptools deprecated that form in favour of a
PEP 639 SPDX expression plus a `license-files` glob, and announced its
removal. A form that is correct when written and deprecated when built is a
build that warns today and fails on some later runner, at whichever moment
someone is trying to cut a release.

**Evidence:** `python -m build --wheel` on the pre-change tree emitted four
deprecation warnings, every one of them about the licence declaration. After
the migration it emits none, and the resulting wheel's `METADATA` carries
`License-Expression: Apache-2.0` and `License-File: LICENSE`, with the text
itself packaged at `planlint-0.2.0.dist-info/licenses/LICENSE`. That last
part is the substantive change, not a cosmetic one: the table form put a
string in the metadata, the new form puts the licence file inside the
distribution.

**The blocker on record no longer applies, and that has been checked rather
than assumed.** `docs/next-steps.md` item 15 says the migration "was
attempted and backed out because the SPDX form makes setuptools require
`packaging>=24.2` at build time, which could not be verified in the
environment available (a distro-managed `packaging` 24.0 that cannot be
upgraded)." That premise is stale. `python -m build` resolves
`[build-system] requires` in an isolated environment, installing a modern
setuptools and packaging regardless of what the ambient interpreter ships, so
the ambient version is irrelevant to the build the wheel actually comes from.
The same item required the floor raise to land in the same commit as the form
switch; it does.

**The obvious fail-closed criterion is false, and that is the interesting
part of this change.** "A build with no `LICENSE` file fails" was written
down, tested, and disproved: setuptools accepts a `license-files` glob that
matches nothing and produces a wheel with no licence at all, silently and at
exit 0. So the migration cannot be gated at the build. It is gated at the
artifact instead, by a new script that opens every built wheel and asserts
what it must contain.

## What Changes

- **`pyproject.toml`** — `license = { text = "Apache-2.0" }` becomes the PEP
  639 SPDX string `license = "Apache-2.0"`, joined by `license-files =
  ["LICENSE"]`, which is what puts the licence text inside the wheel's
  `.dist-info/licenses/` directory. `[build-system] requires` is raised from
  `setuptools>=68` to `setuptools>=77` — the floor that understands both — in
  the same commit, with a comment recording why (a floor without the SPDX
  string buys nothing; the SPDX string without the floor fails to build on an
  old setuptools instead of merely warning). The `License :: OSI Approved ::
  Apache Software License` classifier is removed, because PEP 639 forbids
  pairing a `License ::` classifier with an SPDX expression and a modern
  setuptools rejects the pair outright. A comment in `classifiers` records
  the absence, so nobody helpfully adds it back.
- **`tools/check_wheel_metadata.py`** (new) — the fail-closed gate. Opens
  every wheel in a given directory and reports a violation when
  `License-Expression` is missing from `METADATA` or does not match the
  expression declared in `pyproject.toml`, when a legacy `Classifier: License
  ::` line survives, or when a file named by `license-files` is absent from
  `.dist-info/licenses/` or present but empty. The expected expression is
  read from the project rather than restated in the script, so the gate
  cannot drift from the source of truth. Exit 0 clean, 1 on a violation, 2
  when the check could not run — the same three-way contract the CLI itself
  publishes.
- **`Makefile`** — a new `wheel-check` target that builds the wheel and runs
  the gate over `dist/`.
- **`.github/workflows/ci.yml`** — a new `packaging` job that installs the
  build frontend, builds the wheel in an isolated environment, and runs the
  gate. On every pull request, because licence metadata is only observable in
  a built artifact and the release workflow was previously the only place
  that ever built one.
- **`.github/workflows/release.yml`** — the same gate as a step in the build
  job, before anything is uploaded. Index versions are immutable; a licence
  defect discovered after the upload cannot be fixed in place.
- **`tests/test_wheel_metadata.py`** (new) — twelve tests. Synthetic,
  in-memory wheels for each violation the gate claims to catch, the CLI's
  three-way exit contract, and one end-to-end test that builds this project
  for real and gates the result, so the synthetic fixtures cannot drift into
  testing a shape setuptools no longer emits.
- **`CHANGELOG.md`** — an `[Unreleased]` entry recording the metadata change,
  the new gate, the measured warning count, and the false criterion.

## Non-Goals

- **No change to the licence.** The project stays Apache-2.0 and `LICENSE`
  keeps its text and its path. This changes how the licence is *declared*,
  not what it is.
- **No `sdist` metadata gate.** The gate reads wheels. An sdist carries the
  same declaration through the same code path, and adding a second archive
  format to the script would double its surface for a case no evidence points
  at; the release workflow builds both and the wheel is the artifact the
  smoke test installs.
- **No TOML parser.** The gate scans `pyproject.toml` line by line rather
  than parsing it. This project targets Python 3.10, where `tomllib` is not
  in the stdlib, and it has no runtime dependencies to spend a backport on
  for one gate script — the same reasoning the existing threshold scanners
  already use.
- **No SPDX expression validation.** The gate compares the wheel's expression
  against the project's declaration; it does not check that the string is a
  well-formed SPDX identifier. Validating SPDX syntax is setuptools' job on
  the way in, and a second, weaker implementation of it here would be a
  source of false confidence.
- **No roadmap rewrite beyond item 15.** `docs/next-steps.md` item 15 is the
  one entry this change invalidates and the one entry it owes an edit; the
  rest of the roadmap is untouched. As of this writing that edit is still
  **outstanding** — item 15 on disk still opens "`pyproject.toml` still uses
  the `license = { text = ... }` table form", which the shipped
  `pyproject.toml` contradicts. `AC-LM-9` covers closing it.

## Affected Capabilities

- `license-metadata`
