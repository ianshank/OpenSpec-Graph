---
name: planlint-add-phrasing-case
description: Add a labelled sentence to planlint's phrasing corpus under tests/fixtures/phrasing/, re-measure the G002 and U004 matchers with tools/matcher_accuracy.py, and adjust a negation pattern or an accuracy floor in pyproject.toml when the evidence says so. Use when a criterion is wrongly counted as non-success (or wrongly not), when a requirement is wrongly read as normative, or when adding a pattern to NEGATION_PATTERNS.
---

# Adding a phrasing case and re-measuring the matchers

Two rules read English prose: G002 (`Criterion.is_negative`) and U004/S003
(`Requirement.is_normative`). Their accuracy is a measured number held to
floors in `pyproject.toml` under `[tool.specgraph]`, not a claim. The flat
pattern list this replaced scored precision 0.38 and silenced G002 on
"the block renders below the header" — so every change to a pattern is a
change to a number, and the number is what gets reviewed.

## Steps

1. **Label from the sentence alone, before running the matcher.** For a
   criterion: does it assert a non-success outcome? For a requirement: does it
   use SHALL or MUST as a modal? That second question is the rule's actual
   contract (its message says "uses no SHALL/MUST"); a requirement that is
   normative in spirit without those words belongs in
   `tests/fixtures/phrasing/requirements-modal-variants.jsonl`, which asserts
   nothing. A sentence you cannot label confidently belongs in
   `tests/fixtures/phrasing/criteria-ambiguous.jsonl`, likewise unscored.
   A row added because it makes the number move is not evidence.
2. **Append the row** to `tests/fixtures/phrasing/criteria.jsonl` or
   `tests/fixtures/phrasing/requirements.jsonl`: one JSON object per line
   with `text` (and `body` for a requirement), a boolean `label`, and a
   `note` saying why. Keep the file `-text` in git (already set in
   `.gitattributes`).
3. **Measure**: `make matcher-accuracy`. It prints precision and recall per
   rule and, per negation pattern, how many labelled sentences it hit and how
   many it misfired on. Read the misfires; that column is the review.
4. **If a pattern must change**, edit `NEGATION_PATTERNS` in
   `openspec_graph/parse_semantics.py`. Put it in the right tier —
   *annotation* only if it reads the criterion's own marker, *structural* only
   with zero measured false positives, *lexical* otherwise, restricted to
   verbal inflections and refusing a following hyphen. Give it a unique
   `name`; the name is the reporting key. Every pattern is compiled
   `re.IGNORECASE`; `tests/test_matcher_accuracy.py` fails otherwise.
5. **Check the repo's own tree still passes.** `make validate` runs G002 over
   every change package here; a pattern removed or tightened must not strip
   the last non-success criterion from any of them.
6. **If a floor must move**, edit the four `*_pct` keys in `pyproject.toml`
   `[tool.specgraph]`. Raise freely once the measurement is stable. Lowering
   one needs a reason in the commit message, because it means the matcher got
   worse. Never put the number anywhere else: `make thresholds` fails on a
   threshold in the Makefile or workflow YAML.
7. **Record the measurement** in `tests/fixtures/phrasing/README.md`'s table
   and `docs/aqa.md`'s matcher section if it changed materially, and add the
   sentence to `README.md`'s "And what it got wrong" ledger if it exposed a
   real false-fire.
8. **Run `make pre-pr`** before considering the case done.

The corpus is adversarial by construction and synthetic; the README says so.
It is a regression net, not a benchmark, and the tier a pattern lives in is
the design decision the number defends.
