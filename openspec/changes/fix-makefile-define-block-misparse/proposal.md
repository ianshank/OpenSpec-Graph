# Change: Fix Makefile `define`/`endef` Block Misparse

## Why

Neither `machinery.py`'s structural parser nor `detect.py`'s pre-existing
regex fallback recognized GNU Make's `define VARNAME ... endef` construct.
A `define` block's body is commonly written at column 0 with no leading
tab (unlike a recipe line), so a body line containing a colon — e.g. a
help-text block's `Usage: make test` — is indistinguishable from a real
rule line to both parsers, and gets fabricated into `make_targets` as a
target that does not exist.

**Evidence:** confirmed directly against the live 109-line `machinery.py`:
a `define HELP_TEXT\nUsage: make test\nendef\n` fixture added `"Usage"` to
`MakefileFacts.targets` before this change. A fabricated target is not
merely cosmetic — it can cause G004 (`_unknown_make_target`) to silently
pass a spec that cites a `make` target that isn't real, since the target
now (incorrectly) appears to exist.

The bug is not confined to `machinery.py`: a `define` block lowers
structural-parse confidence, which triggers `detect.py`'s
`_make_target_facts()` to widen the result by unioning in
`_legacy_make_targets()` — a plain regex with the identical `define`/
`endef` blindness, which independently re-fabricates the same bogus
target. Fixing `machinery.py` alone leaves the end-to-end `detect.profile()`
path still broken for this case; both call sites need the fix.

## What Changes

- `openspec_graph/machinery.py`: track an `in_define` boolean across the
  line-scan loop; skip every line (rule-matching included) between a line
  matching `^define\b` and its matching `^endef\b`, mirroring how
  recipe-body lines are already skipped. A `define` block also lowers
  confidence — new `has_define: bool = False` field on `MakefileFacts`
  (defaulted, additive; the one existing positional constructor call in
  `detect.py` keeps working unchanged), included in the `confidence`
  property's low-confidence condition alongside `has_include`/
  `has_conditional`.
- `openspec_graph/detect.py`: `_legacy_make_targets()` strips
  `define...endef` block bodies (via a new `_DEFINE_BLOCK` regex) before
  running its target-extraction regex, closing the identical gap in the
  fallback path.

## Non-Goals

- No handling for an *unterminated* `define` (no matching `endef`) beyond
  graceful, asymmetric degradation: this is already a malformed Makefile
  from GNU Make's own perspective. `machinery.py` stays `in_define` for
  the rest of the file (nothing after the unterminated block resolves);
  `_legacy_make_targets()`'s regex leaves the unterminated text unmodified
  (its own extraction may pick up spurious matches within it). Neither
  behavior is engineered further for an already-broken input.
- No change to recursive `$(MAKE)` sub-invocations or target-specific
  pattern substitution (`%.o: %.c`) — both remain correctly out of scope
  per the existing DEC-MP-004 pattern-rule exclusion and the recipe-line
  skip that already treats indented lines as opaque.

## Affected Capabilities

- `makefile-define-blocks`
