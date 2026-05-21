.PHONY: build publish publish-test clean test

build: clean
	python3 -m build

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository testpypi dist/*

test:
	python3 -c "from sessemi import Sessemi; print('import ok')"
	sessemi --version

clean:
	rm -rf dist/ build/ *.egg-info sessemi.egg-info/
