# Labelled target-repository corpus

Each subdirectory is one synthetic **target repository** (`repo/`) plus the
dialect card `planlint detect` is expected to produce for it
(`expected.json`). `tests/test_detect_corpus.py` runs `detect.profile()` over
every shape and diffs the result against the expectation.

## Why this exists

Before this corpus, `detect` had been exercised against two real repositories
and a handful of inline fixtures. A one-sitting probe over twenty synthetic
shapes found five wrong detections and two crashes, one of which produced a
**false `G004`** ("cites `make all` which is not a target") against a
perfectly valid repository. Detection is the load-bearing primitive — `G003`'s
threshold locator, `G004`'s target existence, `G005`'s invariant source and
`H001`'s runnable stage are each only as correct as the card underneath them —
so it needs labelled input rather than confidence.

## How an expectation works

`expected.json` is a **partial** card: it asserts only the fields that shape
is actually about, and `dialect_card.diff_cards()` ignores every field absent
from the baseline. A shape about BOM handling therefore pins `make_targets`
and nothing else, so an unrelated schema addition does not churn thirteen
files. `schema_version` is injected by the test and pinned once, centrally.

The expectation is written from what a correct detector **should** report,
not from what the code currently does. Four of these shapes failed when they
were first written; the fixes landed with them.

## The shapes

| Shape | What it pins | Why |
|---|---|---|
| `bom-rule-first` | `make_targets` = all, build, test | U+FEFF is a format character, not whitespace, so `str.strip()` leaves it and it became part of the first target name. The mangled name then produced a false `G004`. |
| `bom-phony-first` | `make_targets` = build, test | Same defect in its more dangerous form: a BOM-prefixed `.PHONY` misses the special-target filter and becomes a target. |
| `crlf-makefile` | `make_targets` = all, build | Carriage returns must not survive into target names. |
| `float-coverage-floor` | `threshold.value` = 85.5 | coverage.py accepts a fractional floor. Truncating 85.5 to 85 silently **loosens** the gate being reported. |
| `integral-coverage-floor` | `threshold.value` = 90 (int) | The float fix must not widen integral floors to `90.0`; the card is a byte-stability contract and saved `--diff` baselines must stay clean. |
| `foreign-table-fail-under` | `threshold` = null | `fail_under` under an unrelated TOML table is not this repo's coverage floor. It used to be reported under a locator naming `[tool.coverage.report]`, a table that did not exist in the file. |
| `coveragerc-floor` | locator + value | `.coveragerc` uses a bare `[report]`. |
| `setup-cfg-floor` | locator + value | `setup.cfg` namespaces it as `[coverage:report]`. Different section names, deliberately not unified. |
| `hostile-makefile` | targets parsed, **nothing executed** | `$(shell rm -rf …)`, a bare `$(shell touch …)`, `$(eval $(shell …))`, `.SHELLFLAGS` and `.ONESHELL`. GNU Make evaluates these at parse time even under `-n`, so this is the specimen that turns "parsing never executes" from a code-review claim into an assertion. The test rewrites `@@CANARY@@` to a real directory and proves it survives. |
| `include-chain` | targets = all, confidence `low` | Includes are flagged, never followed. A documented limit, pinned so changing it is a decision rather than a drift. |
| `define-block-fake-targets` | targets = build, define-thing | A colon inside a `define` body is opaque replacement text, not a rule. `define-thing:` is a real target whose name merely starts with the directive keyword. |
| `node-vitest-no-makefile` | languages = node, no targets, no threshold | Stages come from a Makefile and thresholds from the Python/policy locators. A documented limit. |
| `jvm-gradle-jacoco` | languages = jvm, no threshold | The language is detected; the JaCoCo `violationRules` minimum is not a supported threshold locator. A documented limit. |
| `bom-coveragerc-floor` | locator + value | A BOM-prefixed `.coveragerc` reached configparser as `﻿[report]`, raised `MissingSectionHeaderError`, and the floor silently read as absent. Same defect class as the Makefile BOM. |
| `multiline-string-fail-under` | `threshold.value` = 90 | `exclude_lines = """…"""` is a free-text list that lives in exactly this table; a `fail_under = 42` line inside the string must be opaque, not the floor. |
| `multiline-array-fail-under` | `threshold.value` = 90 | An array element that looks like a table header (`"[not a table]"`) must not reset the current table, and one that looks like a key must not become the floor. |
| `quoted-table-header` | `threshold.value` = 90 | `["tool"."coverage"."report"]` is the same table spelled with quoted segments. |
| `inline-table-fail-under` | `threshold` = null | `report = { fail_under = 90 }` is valid TOML the scanner does not read. Pinned as a documented limit (`docs/next-steps.md` 7a) so supporting it is a decision. |
| `array-of-tables-fail-under` | `threshold` = null | `[[tool.coverage.report]]` is an array of tables, never the table holding a floor. |
| `quoted-string-fail-under` | `threshold` = null | `fail_under = "90"` is a string; coverage.py rejects it and so does planlint, rather than guessing. |

Three further cases are generated inside the test rather than committed,
because a directory cannot be represented as a file in git and a large
specimen should not be: a directory named `Makefile`, a directory named
`pyproject.toml` (both of which used to raise `IsADirectoryError` and exit 1),
and a Makefile large enough to catch a pathological parser regression.

## Adding a shape

Write `repo/`, state the expectation in the table above, hand-write
`expected.json` from that expectation, then run the suite. If it fails,
decide which side is wrong before touching either.
