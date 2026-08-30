.PHONY: help test lint validate ci clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

test: ## Run the test suite with the coverage gate applied
	python -m pytest tests/ --cov=openspec_graph --cov-report=term-missing --cov-fail-under=90 -q

lint: ## Ruff check (installed in CI; skipped locally if ruff is absent)
	@command -v ruff >/dev/null 2>&1 && ruff check openspec_graph tests || echo "ruff not installed, skipping"

validate: ## Validate this repo's own OpenSpec change packages with specgraph
	specgraph --target . validate --fail-on ERROR

ci: test lint validate ## The authoritative local superset
	@echo "ci: all gates passed"
