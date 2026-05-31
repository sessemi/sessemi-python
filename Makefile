.PHONY: build publish publish-test release clean test

build: clean
	python3 -m build

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository testpypi dist/*

# Usage: make release VERSION=1.3.0
# Tags HEAD as v$(VERSION), publishes to PyPI, pushes commit + tag.
# The package version is derived from the tag by setuptools_scm at build time —
# no source files reference a version literal, nothing to bump.
# Halts on a dirty working tree or if the tag already exists.
release:
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

test:
	python3 -c "from sessemi import Sessemi; print('import ok')"
	sessemi --version

clean:
	rm -rf dist/ build/ *.egg-info sessemi.egg-info/
