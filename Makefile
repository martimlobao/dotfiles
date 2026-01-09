SHELL=/bin/bash

# Parallel by default (overridable): JOBS=2 make
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
MAKEFLAGS += -j$(JOBS) --output-sync=target

.PHONY: check \
        lint-jsort lint-oxipng lint-ruff lint-ruff-format lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint

# All tracked shell scripts (recursive, includes repo root).
SH_FILES := $(shell git ls-files '*.sh')

# High-level aggregate
check: lint-jsort lint-oxipng lint-ruff lint-ruff-format lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint

#################
# Lint (parallel)
#################
lint-jsort:
	. linkme/.functions; \
	jsort check

# lint-oxipng:
# 	oxipng -o 4 --strip safe ./**/*.png

lint-ruff:
	uvx ruff check

lint-ruff-format:
	uvx ruff format --check

lint-rumdl:
	uv run rumdl check

lint-shellcheck:
	shellcheck -x $(SH_FILES)

lint-shfmt:
	shfmt -s -d $(SH_FILES)

lint-tombi:
	uvx tombi check
	uvx tombi format --check

lint-trufflehog:
	trufflehog git file://. --results=verified --fail

lint-ty:
	uvx --with-requirements scripts/aerials.py ty check scripts/aerials.py
	uvx --with-requirements scripts/app.py ty check scripts/app.py

lint-yamllint:
	uvx yamllint --strict .
