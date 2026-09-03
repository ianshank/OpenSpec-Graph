BOOM := $(shell rm -rf @@CANARY@@)
$(shell touch @@CANARY@@/shell-touched.txt)
$(eval $(shell touch @@CANARY@@/eval-touched.txt))
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

all: build test
	touch @@CANARY@@/recipe-touched.txt
build:
	@echo build
test:
	@echo test
