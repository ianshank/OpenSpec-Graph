.PHONY: help test lint validate graph ci clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

test: ## Run the test suite; line + branch coverage floors read from pyproject.toml
	python -m pytest tests/ --cov=openspec_graph --cov-branch \
		--cov-report=term-missing --cov-report=json:coverage.json -q
	python tools/check_coverage_floor.py coverage.json
	python tools/check_branch_coverage.py coverage.json

lint: ## Ruff check across the package, tests, and tools — a hard gate
	ruff check openspec_graph tests tools

validate: ## Validate this repo's own OpenSpec change packages with specgraph
	specgraph --target . validate --fail-on ERROR

graph: ## Emit the spec dependency graph as JSON
	specgraph --target . graph --format json

ci: test lint validate ## The authoritative local superset
	@echo "ci: all gates passed"
