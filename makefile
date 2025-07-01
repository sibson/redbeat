.PHONY: upload release release-test release-tag build version

REQUIREMENTS_TXT=requirements-dev.txt

test: unittests

lint: venv
	$(VENV)/flake8 redbeat tests

build:
	$(VENV)/python -m build

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
	echo "usage: make release VERSION='M.m.p'"
else
	sed -i '' -e 's|version = .*|version = $(VERSION)|' setup.cfg
	sed -i '' -e "s/unreleased/$(TODAY)/" CHANGES.txt
	git ci -m"prepare for release of $(VERSION)" CHANGES.txt setup.cfg
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags
	echo "$(VERSION)dev (unreleased)\n---------------------\n$(cat CHANGES.txt)\n  -\n\n" > CHANGES.txt
endif

docs:
	$(MAKE) -C docs/ html

unittests: venv
	$(VENV)/python -m unittest discover tests

clean:
	rm -f dist/*
	rm -rf docs/_build docs/_static docs/_templates

veryclean: clean clean-venv

include Makefile.venv

version:
	@grep -m1 '^version' setup.cfg | sed 's/.*= *//'
