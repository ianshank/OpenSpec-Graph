# Tasks — Decompose God Files

- [ ] Phase 1: shared test fixtures — `tests/support.py` + `tests/fixtures/`;
      remove triplicated inline `MAKEFILE`/`PYPROJECT`/spec blobs; keep green.
- [ ] Phase 2: split `scaffold.py` templates into `scaffold_templates.py`;
      keep `scaffold.py` as the write layer.
- [ ] Phase 3: extract `graph.build_graph` into private helpers; output unchanged.
- [ ] Phase 4: split `parse.py` into `parse_model`/`parse_harness`/
      `parse_upstream`/`parse_semantics`; keep `parse.py` as facade.
- [ ] Phase 5: split `rules.py` into `rule_types`/`rules_generic`/
      `rules_harness`/`rules_upstream`; keep `rules.py` as registry/facade.
- [ ] Add guard tests: public import compatibility, byte-identical output,
      import boundaries, fixture dedup, new-modules stdlib-only.
- [ ] `make pre-pr` green; push; open PR; confirm CI green.
