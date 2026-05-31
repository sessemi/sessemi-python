.PHONY: build publish publish-test release clean test

build: clean
	python3 -m build

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository testpypi dist/*

# Usage: make release VERSION=1.3.0
# Bumps __version__, commits, tags v$(VERSION), publishes to PyPI, pushes commit + tag.
# Halts on a dirty working tree or if VERSION matches the current __version__.
release:
ifndef VERSION
	$(error Usage: make release VERSION=X.Y.Z)
endif
	@if [ -n "$$(git status --porcelain)" ]; then echo "❌ Working tree not clean — commit or stash first."; exit 1; fi
	@if grep -q '^__version__ = "$(VERSION)"$$' sessemi/__init__.py; then echo "❌ Already at $(VERSION)."; exit 1; fi
	@sed -i.bak 's/^__version__ = .*/__version__ = "$(VERSION)"/' sessemi/__init__.py && rm sessemi/__init__.py.bak
	@grep -q '^__version__ = "$(VERSION)"$$' sessemi/__init__.py || (echo "❌ Version bump did not apply."; exit 1)
	@git add sessemi/__init__.py && git commit -m "release: v$(VERSION)"
	@git tag v$(VERSION)
	@$(MAKE) publish
	@git push && git push --tags
	@echo "✅ Released v$(VERSION) → PyPI + origin"

test:
	python3 -c "from sessemi import Sessemi; print('import ok')"
	sessemi --version

clean:
	rm -rf dist/ build/ *.egg-info sessemi.egg-info/
