# Milestones

## Milestone 1 — Fix broken/stale adopter-facing artifacts  [DONE]

- `templates/spec-gate.yml`: removed literal backticks from all three `run:`
  steps (the substitution on the `validate` step was silently dropping
  `--fail-on ERROR`); replaced the nonexistent `pip install openspec-graph`
  with the install form README already demonstrates
  (`pip install git+https://github.com/ianshank/OpenSpec-Graph`);
  `specgraph` → `planlint` throughout.
- `Dockerfile`: all four stale `specgraph` mentions (build/run comments,
  `ENTRYPOINT`) → `planlint`.
- `.pre-commit-config.yaml`: the `specgraph-validate` hook's `entry:` line →
  `planlint`; hook `id:`/`name:` fields deliberately left unchanged
  (C-AA-1).
- `openspec_graph/detect.py` module docstring (a third, never-shipped name,
  `` `graft detect` ``) and `.github/workflows/ci.yml`'s `self-validate` job
  comment → `planlint`.

- **Gate:** `make pre-pr` green.

## Milestone 2 — Doc/reality sync  [DONE]

- `README.md:135` and `docs/differentiation-roadmap.md:73`: reworded the
  dangling `docs/specs/SPEC_TEMPLATE.md` reference in place to cite
  `tests/fixtures/good_harness.md` and `tests/fixtures/good_upstream.md` —
  both dialects,
  since a real template would need to cover both.
- `docs/architecture/c4.md`: rewrote the module map to show the facade
  pattern `decompose-god-files` actually produced (17 files, not 8).
- `CHANGELOG.md`: added `[Unreleased]` entries for PR #5
  (`rename-cli-and-positioning`) and PR #4 (`decompose-god-files`),
  newest-first above the existing entries.
- `LICENSE`: filled `[yyyy]` → `2026` and `[name of copyright owner]` →
  `Ian Shank` (proposed default, flagged for confirmation — see proposal
  Non-Goals).
- Confirmed no action needed on the `v0.1.0` release tag/link (verified live
  against the GitHub remote).

- **Gate:** `make docs-check` green; the new spec for this change passes its
  own rules (`planlint validate`).
