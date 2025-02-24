.PHONY: upload release release-test release-tag build

REQUIREMENTS_TXT=requirements-dev.txt

test: unittests

version:
ifdef VERSION
	sed -i  -e 's|version = .*|version = $(VERSION)|' setup.cfg
	#git ci setup.py -m"bump version to $*"
else
	echo "usage: make version VERSION='M.m.p'"
endif

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
	sed -i -e "s/unreleased/$(TODAY)/" CHANGES.txt
	git ci -m"update release date for $(VERSION) in CHANGES.txt" CHANGES.txt
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags
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
