.PHONY: upload release release-test release-tag build version setup lint test unittests docs clean veryclean clean-venv release-check

REQUIREMENTS_TXT=requirements-dev.txt

test: unittests

setup:
	python -m pip install --upgrade pip
	pip install -r requirements-dev.txt
	pip install -e .

lint:
	flake8 redbeat tests

build:
	python -m pip install --upgrade build && python -m build

release: release-check unittests release-tag
release-check:
	# ensure latest code
	git pull
	# ensure no local changes
	test -z "`git status --porcelain`"
	$(MAKE) test

release-tag: TODAY:=$(shell date '+%Y-%m-%d')
release-tag:
ifndef VERSION
	@echo "usage: make release VERSION='M.m.p'" && false
else
	sed -i '' -e 's|version = .*|version = $(VERSION)|' setup.cfg
	sed -i '' -e "s/unreleased/$(TODAY)/" CHANGES.txt
	git ci -m"prepare for release of $(VERSION)" CHANGES.txt setup.cfg || git commit -m"prepare for release of $(VERSION)" CHANGES.txt setup.cfg
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags
	printf "%s\n%s\n%s\n  -\n" "$(VERSION)dev (unreleased)" "---------------------" "$$(cat CHANGES.txt)" > CHANGES.txt
endif

docs:
	$(MAKE) -C docs/ html

unittests:
	python -m unittest discover tests

clean:
	rm -f dist/*
	rm -rf docs/_build docs/_static docs/_templates

veryclean: clean clean-venv

clean-venv:
	rm -rf .venv

version:
	@grep -m1 '^version' setup.cfg | sed 's/.*= *//'
