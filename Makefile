SHELL=/bin/bash

# Parallel by default (overridable): JOBS=2 make
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
MAKEFLAGS += -j$(JOBS) --output-sync=target

.PHONY: check \
        check-jsort check-oxipng check-ruff check-ruff-format check-rumdl check-shellcheck check-shfmt check-tombi check-trufflehog check-ty check-yamllint

# High-level aggregate
check: check-jsort check-oxipng check-ruff check-ruff-format check-rumdl check-shellcheck check-shfmt check-tombi check-trufflehog check-ty check-yamllint

#################
# Lint (parallel)
#################
check:

check-jsort:
	. linkme/.functions; \
	jsort check

# check-oxipng:
# 	oxipng -o 4 --strip safe ./**/*.png

check-ruff:
	uvx ruff check

check-ruff-format:
	uvx ruff format --check

check-rumdl:
	uv run rumdl check

check-shellcheck:
	shellcheck -x ./**/*.sh

check-shfmt:
	shfmt -s -d ./**/*.sh

check-tombi:
	uvx tombi check
	uvx tombi format --check

check-trufflehog:
	trufflehog git file://. --results=verified --fail

check-ty:
	uvx --with-requirements scripts/aerials.py ty check scripts/aerials.py
	uvx --with-requirements scripts/app.py ty check scripts/app.py

check-yamllint:
	uvx yamllint --strict .
