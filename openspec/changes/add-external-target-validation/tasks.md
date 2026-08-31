# Milestones

## Milestone 1 — Read-only proof  [DONE]

The claim that this tool is safe to point at an unfamiliar clone is currently
carried by a module docstring. Make it a test first, before pointing it at
anything unfamiliar.

- Add a test that patches `subprocess.run` and `subprocess.Popen` to raise, and
  patches socket creation to raise, then runs `detect`, `validate`, and `graph`
  against a fixture target. Follow the shape of the existing AC-MP-2 test, which
  patches the process-execution surface and asserts a marker file never appears.
- Hash the target tree before and after each verb and assert equality, so a
  write-then-restore cannot pass.

- **Gate:** `make test` green; the new tests fail when the patches are removed
  and a deliberate write is introduced.
- **Landed:** `tests/test_read_only_guarantee.py`, 18 tests. Five read-only
  verb invocations are each run with `subprocess.run`/`Popen`/`call`/
  `check_output`, `os.system` and `os.popen` patched to raise, and again with
  `socket.socket`/`create_connection`/`getaddrinfo` patched to raise. Two
  mutation checks prove each guard can fail; the socket one connects to
  loopback so it stays runnable with egress blocked. The tree fingerprint
  carries size, mtime_ns and sha256, and a dedicated test shows a
  byte-identical write-then-restore is still caught -- content hashing alone
  would pass it.

## Milestone 2 — Synthetic fixture repository  [DONE]

- Build the fixture on the existing `repo` pytest fixture's shape: a `Makefile`
  declaring a target set, a manifest carrying the coverage floor at its detected
  locator, a contract file declaring invariant lines, and an
  `openspec/changes/<change>/specs/<capability>/spec.md` tree.
- Add a five-file package variant carrying `design.md` and `review.md` alongside
  the three canonical files, so H006 and `detect_dialect` are exercised against a
  shape this repository's own corpus does not contain.
- Produce failing variants by targeted `.replace()` mutation of a passing
  fixture, the pattern `tests/test_graft.py` already uses for one negative
  fixture per rule, rather than hand-authoring each broken spec.

- **Gate:** `make test` green; one passing and one failing fixture per rule.
- **Landed:** `tests/test_external_corpus.py`, 22 tests. A mutation table
  carries one targeted substitution per rule, each asserted unique, with the
  passing fixture proven clean of that rule first. G006 is whole-tree and gets
  its own test. `test_the_mutation_table_covers_every_rule` fails if a rule is
  added without a negative, so the count is never hard-coded -- the rule set
  grew from 16 to 18 during this work, which is why.

## Milestone 3 — External corpus run  [DONE]

- Run `planlint --target <agents-clone> detect --json` and record the emitted
  `StackProfile`: dialect, threshold locator, focused and full stage, invariant
  source, languages.
- Run `planlint --target <agents-clone> validate --fail-on ERROR` and triage
  every finding. Record specifically whether the five-file shape classifies as
  `harness`, `upstream`, or `mixed`, and whether H006 reports missing sections
  for files it was never designed to read.
- File each false positive as its own change package rather than patching them
  in this one.

- **Gate:** `make validate` green in this repository; a recorded triage for the
  external corpus; the target clone byte-identical after the run.

## Milestone 4 — Documentation correction  [DROPPED — already upstream]

- Dropped: already corrected upstream before this work began. `README.md`,
  `CHANGELOG.md` and the docs all state 18 rules, matching `rules.py`.

- **Gate:** `make pre-pr` green.
