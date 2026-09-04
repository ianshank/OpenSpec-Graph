---
name: planlint-add-detect-shape
description: Add a labelled target-repository shape to planlint's detection corpus under tests/corpus/targets/ and update every location that must stay in sync with it. Use when detect misreads a repository layout, when a new config locator or Makefile construct is supported, or when a documented detection limit is pinned.
---

# Adding a detection corpus shape

`tests/corpus/targets/` is the labelled input `detect` is held to. A probe over
twenty synthetic repositories found five wrong detections and two crashes in
one sitting, one of them a false G004 against a valid repository; the corpus
exists so the next one is found by `make test` rather than by hand. Every
shape is a small real repository plus the **partial** dialect card a correct
detector should emit, and the expectation is written from what *should*
happen, never copied from what the code currently prints.

## Steps

1. **State the expectation first, in words.** Add a row to the shape table in
   `tests/corpus/targets/README.md` naming the shape, the card field(s) it
   pins, and why. If you cannot say what a correct detector should report
   before running it, the shape is not ready. A documented limitation
   ("includes are flagged, never followed") is a legitimate expectation —
   pin it, so changing it later is a decision rather than a drift.
2. **Author the repository** under `tests/corpus/targets/<shape>/repo/`. Keep
   it minimal and textual: only the files that make the shape what it is. If
   the shape needs a directory where a file belongs, an empty directory, or a
   file too large to review, it cannot be committed — add it as a generated
   case inside `tests/test_detect_corpus.py` instead (see the directory and
   large-Makefile tests there).
3. **Hand-write `expected.json`** with only the card fields the shape is
   about. `dialect_card.diff_cards()` ignores fields absent from the
   baseline, so an unrelated schema change does not churn every fixture.
   Do not include `schema_version`; the test injects it and pins it once.
   Field names are `StackProfile.to_card()`'s keys in
   `openspec_graph/detect.py`.
4. **Bytes are the fixture.** A CRLF or BOM specimen must reach the parser
   exactly as written; `.gitattributes` already marks the corpus `-text`.
   Write such files with `printf` or a byte-level writer, never an editor
   that normalises line endings.
5. **Run `python -m pytest tests/test_detect_corpus.py -q`.** If the new shape
   fails, decide which side is wrong *before* touching either: a wrong
   expectation is a labelling error, a wrong detection is a defect that gets
   its own fix and a `fix-*` change package under `openspec/changes/`.
6. **If the fix touched a parser, add a property** to `tests/test_properties.py`
   only when there is an invariant the code claims — "never raises",
   "idempotent", "count independent of depth" — not a restatement of the
   fixture.
7. **Run `make pre-pr`** before considering the shape done.

The expectation is the contract. A shape whose `expected.json` was generated
from the detector asserts only that the code equals itself.
