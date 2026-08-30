# Change: Parse Repo Machinery Structurally (CP-3)

> **Status of this package: design only.** This proposal specifies what a
> future implementation must do and must never do. It does not implement
> `machinery.py`; that is separate, follow-up work once this design is
> reviewed and separately approved. See Non-Goals.

## Why

`docs/differentiation-roadmap.md` names this change ("CP-3") the
highest-leverage v1 change and the second of the roadmap's own "First Three
PRs to Execute," right after the CLI rename (CP-1, already shipped). Today,
`detect.py` finds Makefile targets and `parse_semantics.py` finds hard-coded
thresholds in spec prose by regex over text. That produces two known false
positives — a spec quoting the real coverage floor in prose is flagged
anyway, and citing a `make <target>` on a line shared with other targets
(`foo bar: baz`) silently drops every target on that line, so a legitimate
citation fails G004. The roadmap's own sketch for fixing this suggests
"Makefile parsing reads recipes as an AST (`make -p` parse or a minimal
recipe parser)."

**That suggestion needs correcting before anyone builds it.** `planlint`'s
own stated purpose is being safe to point at a repo you do not own
(`openspec_graph/detect.py`'s module docstring: "Detection is read-only by
contract so that `planlint detect` is always safe to run against an
unfamiliar clone"). Shelling out to real GNU Make to inspect an *untrusted*
target repo's Makefile — even via `-p`, `-n`, or `-q` — does not honor that
promise:

- `$(shell ...)` calls outside a recipe body execute at makefile parse/read
  time, unconditionally — not deferred to recipe execution. A malicious or
  merely messy Makefile can run arbitrary shell commands simply by being
  loaded, regardless of which flags are used to try to avoid *building*
  anything.
- `-p` alone does not even avoid attempting to build the default goal; GNU
  Make's own documented behavior is that `-p` prints the database "then
  execute[s] as usual" — only `make -qp` together avoids that.

  Sources (searched independently three times across this work, converging
  on the same specific manual language each time; direct `gnu.org` access is
  blocked by this sandbox's egress proxy on every attempt, so this is via
  search synthesis rather than a direct fetch of the primary source):
  - [Shell Function (GNU make)](https://www.gnu.org/software/make/manual/html_node/Shell-Function.html)
  - [Reading Makefiles / how make reads a makefile (GNU make)](https://www.gnu.org/software/make/manual/html_node/Reading-Makefiles.html)
  - [Options Summary (GNU make)](https://www.gnu.org/software/make/manual/html_node/Options-Summary.html)

  No flag combination makes shelling out to real `make` safe against an
  adversarial Makefile. Implementing the roadmap's literal suggestion would
  also be a **regression**: `openspec_graph/` currently has zero
  `subprocess`/`shell=True`/`eval`/`exec` calls anywhere in its source.

**Evidence for the false positives this change fixes:** `openspec_graph/detect.py`'s
Makefile-target regex is anchored with `re.MULTILINE`'s `^`, so
`_MAKE_TARGET.findall("foo bar: baz\n")` returns `[]` — both `foo` and `bar`
vanish, not just one — confirmed by direct execution, and it generalizes to
three or more names on one line. `openspec_graph/parse_semantics.py`'s
`MAKE_REF` regex matches the bare English word "make" anywhere in spec
prose, so the ordinary English verb "make" followed by a word like "sure" or
"progress" false-cites a target that isn't in `GENERIC_STAGES` and isn't a
real target, tripping G004 on ordinary prose.

**Real-world calibration:** a separate external-validation pass re-ran
`planlint` against two real, independently-evolving repos
(`Mango_Code_Agent-Harness`, `Mouse-Droid-AGI`). Neither repo's current
Makefile happens to contain a multi-target line, and neither repo's current
spec prose happens to contain a bare, unfenced "make" citation — so both
false-positive classes above are confirmed real (by direct execution against
constructed fixtures) but narrower in day-to-day impact against these two
specific repos *today* than two other gaps the same validation pass found
independently (a body-blind bug in rule U004, and a `.coveragerc`/`setup.cfg`
threshold-detection gap — both filed as separate follow-ups, out of scope
for this change). Worth weighing when this design is prioritized against
other work: it fixes a real and structurally-important class of false
positive, but it is not currently the highest-frequency false positive
observed against real content.

## What Changes (design scope for a future implementation)

- A new module, `openspec_graph/machinery.py`, sitting below `detect.py`
  (which calls it), stdlib-only, doing no I/O of its own — `detect.py` reads
  the Makefile text and hands it in as a string, matching the existing
  `parse_semantics.hard_coded(text)` pattern of pure-text-in.
- **Must safely resolve**: target names including multi-target lines
  (`foo bar: baz` → both), `.PHONY`-declared names, and GNU Make's built-in
  special targets (the existing special-target skip list —
  `.PHONY`/`.DEFAULT_GOAL`/`.SUFFIXES` — extended to the small, stable, full
  set: `.PRECIOUS`, `.INTERMEDIATE`, `.SECONDARY`, `.DELETE_ON_ERROR`,
  `.EXPORT_ALL_VARIABLES`, `.NOTPARALLEL`, `.ONESHELL`, `.POSIX`, `.SILENT`,
  `.IGNORE`).
- **Explicitly declines to resolve, with a safe fallback rather than a
  guess**: recursive variable expansion in target position
  (`$(BINARY): $(SRCS)`), `include`d files (recognized, not followed —
  presence alone lowers confidence rather than opening more files),
  conditional blocks (`ifeq`/`ifdef`: scan both branches and union their
  targets, deliberately biased toward false negatives on "target doesn't
  exist" rather than ever wrongly claiming a real target is missing).
  Recipe body lines (tab-indented lines following a target) are read as
  opaque text only, never interpreted or executed — reading recipe *text* is
  always safe; the risk this design avoids entirely is ever executing it.
- **Fallback signal**: when structural parsing can't confidently resolve a
  target, fall back to today's existing (unchanged) regex path and surface a
  low-confidence signal, rather than hard-failing G004 on something static
  analysis genuinely can't determine. Reuse the existing precedent for an
  unnumbered, non-blocking diagnostic (`cmd_detect`'s current dialect-mismatch
  warning) rather than pre-registering a new rule ID before the feature is
  built and its numbering can be decided in context.
- **Threshold-value comparison** (separable from the Makefile-parsing piece,
  no untrusted-input handling involved): stop flagging a hard-coded number in
  spec prose when it is the single, unambiguous threshold-shaped number on
  that line and it matches the real value already carried by
  `detect.ThresholdSource`. Must not use a naive "does the target value
  appear anywhere in the line" check — a same-line, multi-threshold case
  (e.g. prose describing a change from one percentage to another) can
  otherwise wrongly suppress a genuine violation via coincidental match to
  unrelated text.
- **Prose-citation precision**: tighten the `make`-citation regex to require
  backtick-fencing or the existing `stage:` convention already used
  throughout the `GOOD_HARNESS` fixture, instead of matching the bare English
  word "make" anywhere in prose.

## Non-Goals

- **No implementation in this change package.** This proposal is the
  design; building `machinery.py` is separate, follow-up work, to be scoped
  as its own implementation effort once this design is reviewed. Untrusted
  input handling is the highest-stakes code path in this repo and deserves
  focused review time of its own, not a rushed bundling alongside cheap
  fixes.
- **No shelling out to `make`, in any form, at any confidence level.** Not as
  the primary path, not as a fallback. See Why.
  A `subprocess`/`shell=True` call anywhere in `openspec_graph/` for this
  purpose is rejected outright, not a design tradeoff to weigh.
- **No new rule ID reserved yet.** `G006` is not claimed by this change
  package (the roadmap's `add-waiver-ledger-and-inv-lints` change already
  earmarks `G006` for an orphan-invariant rule); if a low-confidence signal
  from this design does need a formal rule ID rather than an unnumbered
  diagnostic, that is decided when it is actually built, not pre-allocated
  here.
- **No JSON contract change.** `StackProfile.as_dict()`'s `make_targets`
  field keeps its existing `tuple[str, ...]` shape regardless of how it is
  computed, so this does not ripple into the `graph`/`validate` JSON
  contract or the hash pins in `tests/test_decomposition.py`.

## Affected Capabilities

- `machinery-parsing`
