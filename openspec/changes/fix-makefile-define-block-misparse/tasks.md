# Milestones

## Milestone 1 — Fix the structural parser  [DONE]

- `openspec_graph/machinery.py`: `in_define` state tracked across the
  line-scan loop; `has_define` field added to `MakefileFacts` (defaulted);
  `confidence` property extended.
- `tests/test_machinery.py`: 2 new tests (body-not-parsed-as-rule,
  directive/conditional-suppressed-inside-block); existing
  clean-Makefile baseline test extended to assert `has_define is False`.
- **Gate:** `make test` green.

## Milestone 2 — Fix the legacy-regex fallback  [DONE]

- `openspec_graph/detect.py`: `_DEFINE_BLOCK` regex strips `define...endef`
  bodies before `_legacy_make_targets`'s extraction regex runs.
- `tests/test_graft.py`: 1 new end-to-end test through `detect.profile()`.
- **Gate:** `make pre-pr` green; `planlint validate` clean.

## Milestone 3 — Harden against an independent adversarial review  [DONE]

Found before merge, on this same not-yet-shipped feature: Milestones 1-2's
own fix had a quadratic-time DoS in `detect.py`'s regex, plus 3 correctness
bugs (nested blocks, indented `endef`, a hyphenated-target false positive).

- `openspec_graph/machinery.py`: new `strip_define_blocks(text) ->
  (cleaned_text, had_define)` — a single O(n) line-scan with a depth
  counter (not a boolean), replacing both the old per-line `in_define`
  tracking in `parse_makefile` and `detect.py`'s whole-text regex.
  `_DEFINE_START`/`_DEFINE_END` tightened to `define(?:\s|$)`/
  `endef(?:\s|$)` (was `\b`).
- `openspec_graph/detect.py`: `_legacy_make_targets` calls
  `machinery.strip_define_blocks` instead of its own `_DEFINE_BLOCK`
  regex, which is deleted.
- `tests/test_machinery.py`: 5 new tests (nested blocks, space-indented
  `endef`, hyphenated target name, a bounded-time ReDoS-safety test, and
  `strip_define_blocks` tested directly).
- `tests/test_graft.py`: 1 new end-to-end bounded-time test through
  `detect.profile()`.
- **Gate:** `make pre-pr` green; independently re-benchmarked: a 20K-line
  unterminated `define` block went from 32+s to ~0.01s.
