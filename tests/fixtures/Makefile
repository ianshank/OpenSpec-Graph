.PHONY: help test regression ci
help: ## show help
	@echo hi
test: ## run tests
	pytest
regression: ## regression tier
	pytest tests/regression
ci: test regression ## full
	@echo ok
