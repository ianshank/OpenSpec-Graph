.PHONY: help test lint typecheck security validate graph graph-mermaid ci pre-pr docs-check thresholds wheel-check skill-catalog skill-manifests skill-artifacts clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

test: ## Run the test suite; line + branch coverage floors read from pyproject.toml
	python -m pytest tests/ --cov=openspec_graph --cov-branch \
		--cov-report=term-missing --cov-report=json:coverage.json -q
	python tools/check_coverage_floor.py coverage.json
	python tools/check_branch_coverage.py coverage.json

lint: ## Ruff check across the package, tests, and tools — a hard gate
	python -m ruff check openspec_graph tests tools

typecheck: ## mypy with config from pyproject.toml — a hard gate
	python -m mypy openspec_graph tools

security: ## Secret scan (gitleaks if installed, deterministic fallback otherwise)
	python tools/check_secrets.py

validate: ## Validate this repo's own OpenSpec change packages with planlint
	planlint --target . validate --fail-on ERROR

graph: ## Emit the spec dependency graph as JSON
	planlint --target . graph --format json

graph-mermaid: ## Emit the spec dependency graph as a Mermaid flowchart
	planlint --target . graph --format mermaid

ci: test lint validate ## The authoritative local core gate
	@echo "ci: core gates passed"

pre-pr: ci typecheck security docs-check thresholds ## The full enterprise AQA gate before opening a PR
	@echo "pre-pr: all enterprise gates passed"

docs-check: ## Confirm required docs exist and are linked from README
	python tools/check_docs.py

thresholds: ## Confirm no hard-coded thresholds in the Makefile or workflow YAML
	python tools/check_no_hardcoded_thresholds.py

wheel-check: ## Build the wheel and confirm it carries its declared SPDX licence
	python -m build --wheel --outdir dist
	python tools/check_wheel_metadata.py dist

skill-catalog: ## Regenerate the distributable skill's rule catalog from the registry
	python tools/render_rule_catalog.py --write

skill-manifests: ## Regenerate .claude-plugin/ manifests from the package version + SKILL.md
	python tools/render_plugin_manifests.py --write

skill-artifacts: skill-catalog skill-manifests ## Regenerate every generated agent-facing artifact
	@echo "skill-artifacts: catalog and manifests regenerated"

clean: ## Remove build, cache, and coverage artifacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov
	rm -f coverage.json coverage.xml .coverage .coverage.* spec-graph.json spec-findings.json head.json base.json
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
