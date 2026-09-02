# Milestones

## Milestone 1 — Retire the blocker before touching anything

- Reproduce the recorded blocker rather than trusting it: `docs/next-steps.md`
  item 15 says the SPDX form was backed out because setuptools needs a
  `packaging` newer than the machine's distro-managed one. Confirm that
  `python -m build` provisions its own isolated build environment from
  `[build-system] requires`, so the ambient version never participates
  (DEC-LM-005).
- Record the pre-change baseline: run `python -m build --wheel` on the
  unmodified tree and count the licence deprecation warnings, so the
  "warnings went to zero" claim later is a measurement and not a hope
  (R-LM-8).
- **Gate:** a clean baseline build, with the warning count written down.

## Milestone 2 — Switch the declaration and raise the floor, in one commit

- `pyproject.toml`: replace `license = { text = "Apache-2.0" }` with the SPDX
  string `license = "Apache-2.0"` and add `license-files = ["LICENSE"]`
  (R-LM-1).
- `pyproject.toml`: raise `[build-system] requires` to the setuptools floor
  that understands both, in the same commit — a floor without the form buys
  nothing and the form without the floor fails to build rather than warning
  (R-LM-2, DEC-LM-007's sibling reasoning in item 15).
- `pyproject.toml`: delete the `License :: OSI Approved :: Apache Software
  License` classifier and leave a comment in `classifiers` recording the
  deliberate absence, so it does not get helpfully restored (R-LM-3,
  DEC-LM-006).
- Rebuild and confirm: zero licence deprecation warnings, `METADATA` carries
  `License-Expression` and `License-File`, and the licence text is packaged
  under `.dist-info/licenses/` (R-LM-4, R-LM-8).
- Confirm `Dockerfile` still copies `LICENSE`, so the new glob has something
  to match inside the image build.
- **Gate:** a real wheel with the expected metadata.

## Milestone 3 — Disprove the obvious criterion, then build the real gate

- Test the criterion first written down — "a build with no `LICENSE` file
  fails" — and record that it is **false**: setuptools accepts a
  `license-files` glob matching nothing and emits a licenceless wheel at exit
  0. Write the result into `DEC-LM-001` rather than quietly replacing the
  criterion (AC-LM-5).
- `tools/check_wheel_metadata.py`: read every wheel in a directory; report a
  violation for a missing or mismatched `License-Expression`, a surviving
  `Classifier: License ::` line, and a declared licence file that is absent
  or empty. Read the expected expression from `pyproject.toml` with a narrow
  line scan, never a literal and never a TOML parse (R-LM-5, C-LM-2,
  DEC-LM-003).
- `tools/check_wheel_metadata.py`: exit 0 clean, 1 on a violation, 2 when the
  check could not run — an empty directory, a missing directory, or a project
  declaring no expression. The module docstring states why "nothing to check"
  is not a pass (R-LM-6, DEC-LM-002).
- **Gate:** the gate passes against the real wheel and fails against a
  hand-broken copy.

## Milestone 4 — Prove the gate rejects, not just accepts

- `tests/test_wheel_metadata.py`: synthetic in-memory wheels, one per
  violation — missing expression, mismatched expression, legacy classifier,
  missing licence file, empty licence file, no `METADATA` at all — plus the
  affirmative `test_a_correct_wheel_passes` so the negatives cannot pass by
  inertia (AC-LM-3, DEC-LM-007).
- `tests/test_wheel_metadata.py`: the CLI's three-way exit contract, exercised
  through `main()` — 0, 1, and both routes to 2 (AC-LM-4).
- `tests/test_wheel_metadata.py`: one end-to-end `test_the_real_wheel_passes_the_gate`
  that builds this project in an isolated environment, runs the gate, and
  asserts no deprecation warning survived. It skips rather than fails when
  `build` or the network is unavailable, because a missing tool is not a
  licensing defect — CI runs the same path unconditionally (AC-LM-1,
  DEC-LM-007).
- **Gate:** `make test` green, with the synthetic and real paths both
  exercised.

## Milestone 5 — Wire it where a release cannot route around it

- `Makefile`: a `wheel-check` target that builds the wheel into `dist/` and
  runs the gate over it (R-LM-7).
- `.github/workflows/ci.yml`: a new `packaging` job — checkout, Python,
  install the build frontend, build the wheel in an isolated environment, run
  the gate — with a comment recording why it runs per pull request rather
  than per tag (R-LM-7, DEC-LM-004).
- `.github/workflows/release.yml`: the same gate as a step in the build job,
  **before** the upload, with a comment recording that index versions are
  immutable. The duplication with the CI job is deliberate: a tag cut from a
  branch that never opened a PR would otherwise reach the index ungated
  (R-LM-7, DEC-LM-004).
- **Gate:** `make ci` green; both workflow files reviewed by hand, since no
  automated check inspects job contents for this gate (AC-LM-6).

## Milestone 6 — Close the record

- `CHANGELOG.md`: an `[Unreleased]` entry covering the metadata change, the
  measured warning count going to zero, the new gate and its exit-2-on-empty
  rule, and the false "a build without LICENSE fails" criterion (AC-LM-9).
- `docs/next-steps.md` item 15: rewrite it to say the migration landed and
  that the isolated-build-environment argument is what retired the
  `packaging` premise. **Still outstanding** — item 15 on disk continues to
  open "`pyproject.toml` still uses the `license = { text = ... }` table
  form", which the shipped `pyproject.toml` contradicts, so the roadmap
  currently describes a state that no longer exists (R-LM-9, AC-LM-9).
- **Gate:** `make pre-pr` green; `planlint validate` clean with this change
  package present.
