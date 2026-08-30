# Change: Fix U004 Body-Blind Modal Check

## Why

Rule U004 ("requirements are normative") only inspects a requirement's
heading line, never its body paragraph, because the parser's `REQUIREMENT`
regex cannot cross a newline. Measured against a real external repo during a
prior validation pass: 20 of 34 requirements false-fired because their
SHALL/MUST lived in the body prose below a noun-phrase heading — the common
real-world authoring style. This project's own scaffold template happens to
dodge the bug (it crams the modal into the heading), which is exactly why
only self-referential test fixtures never caught it.

**Evidence:** `openspec_graph/parse_semantics.py`'s `REQUIREMENT` regex uses
`re.MULTILINE` without `re.DOTALL`, so its capture group is hard-bounded to
the heading's own line. `openspec_graph/parse_upstream.py` builds
`Requirement(text=m.group(2), ...)` from that heading match alone, and
`openspec_graph/rules_upstream.py`'s `_requirement_without_modal` only ever
inspects `req.text`.

## What Changes

- `Requirement` gains a `body` field (upstream dialect only, defaulted to
  `""`) and an `is_normative` property checking both heading and body text
  for SHALL/MUST, mirroring the existing `Criterion.is_negative` pattern.
- `parse_upstream()` captures the prose beneath each Requirement heading,
  bounded by the next Requirement heading or end of document — the same
  bounded-scan idiom the parser already uses locally for Scenario blocks.
- U004 checks `req.is_normative` instead of re-deriving the SHALL/MUST check
  against heading text alone.

## Non-Goals

- No change to the harness dialect's requirement construction
  (`parse_harness.py`) — harness requirements are correctly single-line by
  their own bullet-list convention, and U004 only applies to the upstream
  dialect.
- No change to U002's or `graph.py`'s existing truncated-summary use of
  `req.text` — both only need the heading summary, not the full body.

## Affected Capabilities

- `u004-body-check`
