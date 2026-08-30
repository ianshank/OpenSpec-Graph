# Milestones

## Milestone 1 — Fix U004's body-blind check  [DONE]

- `openspec_graph/parse_model.py`: `Requirement` gains a defaulted `body: str
  = ""` field and an `is_normative` property checking both `text` and `body`
  for SHALL/MUST.
- `openspec_graph/parse_upstream.py`: `parse_upstream()` now captures the
  prose between each Requirement heading and the next Requirement heading
  (or EOF) into `body`, mirroring the bounded-scan idiom already used
  locally for Scenario blocks.
- `openspec_graph/rules_upstream.py`: `_requirement_without_modal` (U004)
  checks `req.is_normative` instead of the heading text alone.
- `tests/test_graft.py`: new
  `test_u004_does_not_fire_when_the_modal_verb_is_only_in_the_body` proves
  the regression case; the existing
  `test_u004_fires_on_a_non_normative_requirement` (unchanged) continues to
  cover the "neither heading nor body normative" control.

- **Gate:** `make pre-pr` green; `planlint validate` clean.
