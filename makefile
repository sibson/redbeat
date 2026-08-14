.PHONY: upload release release-test release-tag bump-version build version setup lint test unittests docs clean veryclean clean-venv release-check

REQUIREMENTS_TXT=requirements-dev.txt

test: unittests

setup:
	python -m pip install --upgrade pip
	python -m pip install -r requirements-dev.txt
	python -m pip install -e .

# invoke via `python -m` rather than the bare `flake8`/`pip` console scripts, so
# the linter runs under the same interpreter as `make setup` and `make
# unittests`. A bare `flake8` resolves through PATH and can land in an unrelated
# environment (a pipx/uv tool venv, say) that lacks flake8-black/flake8-isort --
# in which case flake8 still exits 0, silently skipping every check CI enforces.
lint:
	python -m flake8 redbeat tests

build:
	python -m pip install --upgrade build && python -m build

release: release-check unittests release-tag
release-check:
	# ensure on main branch
	test "`git rev-parse --abbrev-ref HEAD`" = "main"
	# ensure latest code
	git pull
	# ensure no local changes
	test -z "`git status --porcelain`"
	$(MAKE) test

# VERSION defaults to what pbr derives from git tags (next patch above the
# last release, or the version targeted by a bump-version pre-release tag);
# pass VERSION='M.m.p' to override. Git tags are the source of truth, not
# CHANGES.txt -- use `make bump-version VERSION='M.m.p'` for a minor/major
# release, since pbr can only auto-advance the patch number on its own.
release-tag: TODAY:=$(shell date '+%Y-%m-%d')
release-tag: VERSION:=$(or $(VERSION),$(shell python setup.py --version 2>/dev/null | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+'))
release-tag: NEXT_VERSION=$(shell echo $(VERSION) | awk -F. '{print $$1"."$$2"."$$3+1}')
release-tag:
	@test -n "$(VERSION)" || (echo "usage: make release [VERSION='M.m.p'] -- couldn't detect version from git tags" && exit 1)
	@echo "releasing $(VERSION)"
	sed -i '' -e "1s/.*/$(VERSION) ($(TODAY))/" CHANGES.txt
	git ci -m"prepare for release of $(VERSION)" CHANGES.txt || git commit -m"prepare for release of $(VERSION)" CHANGES.txt || true
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags
	printf "%s\n%s\n%s\n  -\n" "$(NEXT_VERSION) (unreleased)" "---------------------" "$$(cat CHANGES.txt)" > CHANGES.txt
	git commit -m"bump CHANGES.txt to $(NEXT_VERSION) for post-release development" CHANGES.txt
	git push

# Force pbr to target a minor/major release instead of auto-advancing the
# patch number: tags vM.m.p.0a1, a pbr pre-release marker. Every untagged
# build from here computes as M.m.p.0a<N>.dev<commits> until the real
# vM.m.p tag lands via `make release`. Deciding to bump minor/major is a
# human call, so VERSION is required, not inferred.
bump-version:
	@test -n "$(VERSION)" || (echo "usage: make bump-version VERSION='M.m.p'" && exit 1)
	git tag -a v$(VERSION).0a1 -m"target next release version $(VERSION)"
	git push origin v$(VERSION).0a1

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
	@python setup.py --version
