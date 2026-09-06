.PHONY: release release-check bump-version build docs unittests test setup lint clean veryclean clean-venv version

ifeq ($(shell command -v uv 2>/dev/null),)
$(error uv is required. See https://astral.sh/uv/install.sh)
endif

test: unittests

setup:
	uv sync

lint:
	uv run flake8 redbeat tests

build:
	uv build

unittests:
	uv run python -m unittest discover tests

docs:
	uv run $(MAKE) -C docs/ html

# VERSION/NEXT_VERSION are computed once, at parse time, from pyproject.toml
# via `uv version` -- the version lives there now, not in git tags. Use
# `make bump-version BUMP=minor|major` first for a minor/major release,
# since deciding to bump those is a human call, not something to infer.
VERSION := $(shell uv version --bump stable --dry-run --short --no-sync 2>/dev/null)
NEXT_VERSION := $(shell uv version --bump patch --bump dev=0 --dry-run --short --no-sync 2>/dev/null)

release: release-check
	@echo "releasing $(VERSION)"
	uv version --bump stable --no-sync
	sed -i '' -e "1s/.*/$(VERSION) ($(shell date '+%Y-%m-%d'))/" CHANGES.txt
	git add pyproject.toml CHANGES.txt
	git commit -m"prepare for release of $(VERSION)"
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags
	uv version --bump patch --bump dev=0 --no-sync
	printf "%s\n%s\n%s\n  -\n" "$(NEXT_VERSION) (unreleased)" "---------------------" "$$(cat CHANGES.txt)" > CHANGES.txt
	git add pyproject.toml CHANGES.txt
	git commit -m"bump CHANGES.txt to $(NEXT_VERSION) for post-release development"
	git push

release-check:
	# ensure on main branch
	test "`git rev-parse --abbrev-ref HEAD`" = "main"
	# ensure latest code
	git pull
	# ensure no local changes
	test -z "`git status --porcelain`"
	$(MAKE) test

# Force the next release to be a minor/major bump instead of the patch bump
# `release` does on its own. Run this, commit and push, then `make release`.
bump-version:
	@test -n "$(BUMP)" || (echo "usage: make bump-version BUMP=minor|major" && exit 1)
	uv version --bump $(BUMP) --bump dev=0 --no-sync
	git add pyproject.toml
	git commit -m"target next $(BUMP) release, $$(uv version --short --no-sync)"
	git push

version:
	@uv version --short --no-sync

clean:
	rm -f dist/*
	rm -rf docs/_build docs/_static docs/_templates

veryclean: clean clean-venv

clean-venv:
	rm -rf .venv
