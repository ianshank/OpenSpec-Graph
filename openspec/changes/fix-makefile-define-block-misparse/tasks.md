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
