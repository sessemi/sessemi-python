.PHONY: help build publish publish-test release clean test
.DEFAULT_GOAL := help

help: ## Show this help
	@echo "sessemi — Python client. Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: clean ## Build sdist + wheel into dist/
	python3 -m build

# PyPI auth uses an API token from an env var — no interactive name/password prompt.
# Export it first (token starts with "pypi-"):
#   export PYPI_TOKEN=pypi-AgEI...        # for PyPI
#   export TESTPYPI_TOKEN=pypi-...        # separate token for TestPyPI
# The :? guard aborts with a clear message if the var is unset.
# The leading @ keeps the token from being echoed to the terminal.
publish: build ## Build, then upload to PyPI (needs PYPI_TOKEN env var)
	@TWINE_USERNAME=__token__ TWINE_PASSWORD="$${PYPI_TOKEN:?Set PYPI_TOKEN to your pypi-... API token}" twine upload dist/*

publish-test: build ## Build, then upload to TestPyPI (needs TESTPYPI_TOKEN env var)
	@TWINE_USERNAME=__token__ TWINE_PASSWORD="$${TESTPYPI_TOKEN:?Set TESTPYPI_TOKEN to your TestPyPI API token}" twine upload --repository testpypi dist/*

# Usage: make release VERSION=1.3.0
# Tags HEAD as v$(VERSION), publishes to PyPI, pushes commit + tag.
# The package version is derived from the tag by setuptools_scm at build time —
# no source files reference a version literal, nothing to bump.
# Halts on a dirty working tree or if the tag already exists.
release: ## Tag v$(VERSION) + publish to PyPI + push (make release VERSION=X.Y.Z)
ifndef VERSION
	$(error Usage: make release VERSION=X.Y.Z)
endif
	@set -e; \
	if [ -n "$$(git status --porcelain)" ]; then echo "❌ Working tree not clean — commit or stash first."; exit 1; fi; \
	if git rev-parse "v$(VERSION)" >/dev/null 2>&1; then echo "❌ Tag v$(VERSION) already exists."; exit 1; fi
	@git tag v$(VERSION)
	@$(MAKE) publish
	@git push && git push --tags
	@echo "✅ Released v$(VERSION) → PyPI + origin"

test: ## Smoke test: import + CLI version
	python3 -c "from sessemi import Sessemi; print('import ok')"
	sessemi --version

clean: ## Remove dist/, build/, egg-info
	rm -rf dist/ build/ *.egg-info sessemi.egg-info/
