SHELL=/bin/bash

# Parallel by default (overridable): JOBS=2 make
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
MAKEFLAGS += -j$(JOBS) --output-sync=target

.PHONY: check test-app \
        lint-checkov lint-jsort lint-oxipng lint-ruff lint-ruff-format lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint

# All tracked shell scripts (recursive, includes repo root).
SH_FILES := $(shell git ls-files '*.sh')

# High-level aggregate
check: lint-checkov lint-jsort lint-oxipng lint-ruff lint-ruff-format lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint test-app

#################
# Lint (parallel)
#################
lint-checkov:
	uvx checkov --quiet -d .

lint-jsort:
	. linkme/.functions; \
	jsort --sort-arrays check

# lint-oxipng:
# 	oxipng -o 4 --strip safe ./**/*.png

lint-ruff:
	uvx ruff check

lint-ruff-format:
	uvx ruff format --check

lint-rumdl:
	uvx rumdl --config linkme/.config/rumdl/rumdl.toml check .

lint-shellcheck:
	shellcheck -x $(SH_FILES)

lint-shfmt:
	shfmt -s -d $(SH_FILES)

lint-tombi:
	uvx tombi lint .
	uvx tombi format --check .

lint-trufflehog:
	trufflehog git file://. --results=verified --fail

lint-ty:
	uvx --with-requirements scripts/aerials.py ty check scripts/aerials.py
	uvx --with-requirements scripts/app.py ty check scripts/app.py

lint-yamllint:
	uvx yamllint -c linkme/.config/yamllint/config .

test-app:
	uvx --with-requirements tests/test_app.py pytest tests/test_app.py \
		--cov=app_module --cov-report=term-missing --cov-fail-under=95
