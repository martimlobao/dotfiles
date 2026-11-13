SHELL=/bin/bash

# Parallel by default (overridable): JOBS=2 make
JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
MAKEFLAGS += -j$(JOBS) --output-sync=target

.PHONY: check test test-app test-aerials test-finder-views \
        lint-apps lint-checkov lint-jsort lint-oxipng lint-ruff lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint

# All tracked shell scripts (recursive, includes repo root).
SH_FILES := $(shell git ls-files '*.sh')

# High-level aggregate
check: lint-apps lint-checkov lint-jsort lint-oxipng lint-ruff lint-rumdl lint-shellcheck lint-shfmt lint-tombi lint-trufflehog lint-ty lint-yamllint test

#################
# Lint (parallel)
#################
lint-actionlint:
	uvx --from actionlint-py actionlint

# Needs Homebrew; skipped where it isn't installed (e.g. CI).
lint-apps:
	@if command -v brew >/dev/null 2>&1; then uv run scripts/app.py validate; \
	else echo "brew not found; skipping apps.toml validation"; fi

lint-checkov:
	uvx checkov --quiet -d .

lint-jsort:
	@if [ ! -x "$(PWD)/temp/.bin/yq" ] && ! (command -v yq >/dev/null 2>&1 && yq --help 2>&1 | grep -q -- "-P"); then \
		echo "Installing yq to temp/.bin..."; \
		mkdir -p temp/.bin; \
		GOBIN="$(PWD)/temp/.bin" go install github.com/mikefarah/yq/v4@latest; \
	fi
	PATH="$(PWD)/temp/.bin:$$PATH" bash -lc '. linkme/.functions; jsort --sort-arrays check'

# lint-oxipng:
# 	oxipng -o 4 --strip safe ./**/*.png

lint-ruff:
	uvx ruff check
	uvx ruff format --check

lint-rumdl:
	uvx rumdl --config linkme/.config/rumdl/rumdl.toml check .

lint-shellcheck:
	uvx --from shellcheck-py shellcheck -x $(SH_FILES)

lint-shfmt:
	uvx --from shfmt-py shfmt -s -d $(SH_FILES)

lint-tombi:
	uvx tombi lint .
	uvx tombi format --check .

lint-trufflehog:
	trufflehog git file://. --results=verified --fail

lint-ty:
	uvx --with-requirements scripts/aerials.py ty check scripts/aerials.py
	uvx --with-requirements scripts/app.py ty check scripts/app.py
	uvx --with-requirements scripts/tests/test_app.py ty check scripts/tests/test_app.py
	uvx --with-requirements scripts/aerials.py --with-requirements scripts/tests/test_aerials.py ty check scripts/tests/test_aerials.py
	uvx --with-requirements scripts/finder_views.py ty check scripts/finder_views.py
	uvx --with-requirements scripts/finder_views.py --with-requirements scripts/tests/test_finder_views.py ty check scripts/tests/test_finder_views.py

lint-yamllint:
	uvx yamllint -c linkme/.config/yamllint/config .

test-app:
	uvx --with-requirements scripts/app.py --with-requirements scripts/tests/test_app.py \
		pytest scripts/tests/test_app.py

test-aerials:
	uvx --with-requirements scripts/aerials.py --with-requirements scripts/tests/test_aerials.py \
		pytest scripts/tests/test_aerials.py

test-finder-views:
	uvx --with-requirements scripts/finder_views.py --with-requirements scripts/tests/test_finder_views.py \
		pytest scripts/tests/test_finder_views.py

test:
	mkdir -p temp
	COVERAGE_FILE=temp/.coverage.total \
	uvx --with-requirements scripts/app.py --with-requirements scripts/aerials.py \
		--with-requirements scripts/finder_views.py \
		--with-requirements scripts/tests/test_app.py \
		--with-requirements scripts/tests/test_aerials.py \
		--with-requirements scripts/tests/test_finder_views.py \
		pytest scripts/tests/test_app.py scripts/tests/test_aerials.py scripts/tests/test_finder_views.py \
		--cov=app_module --cov=aerials_module --cov=finder_views_module --cov-report=term-missing --cov-fail-under=80
