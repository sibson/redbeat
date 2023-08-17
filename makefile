.PHONY: upload release release-test release-tag upload

VERSION_FILE?=setup.py

version:
	python setup.py --version

version-%: OLDVERSION:=$(shell python setup.py --version)
version-%: NEWVERSION=$(subst -,.,$*)
version-%: 
	sed -i -e s/$(OLDVERSION)/$(NEWVERSION)/ $(VERSION_FILE)
	git ci setup.py -m"bump version to $*"

lint:
	flake8 --count --statistics redbeat tests


release: release-check release-tag upload

release-check:
	git pull
	make test

release-tag: VERSION:=$(shell python setup.py --version)
release-tag: TODAY:=$(shell date '+%Y-%m-%d')
release-tag:
	sed -i -e "s/unreleased/$(TODAY)/" CHANGES.txt
	git ci -m"update release date for $(VERSION) in CHANGES.txt" CHANGES.txt
	git tag -a v$(VERSION) -m"release version $(VERSION)"
	git push --tags

upload: VERSION:=$(shell python setup.py --version)
upload:
	python setup.py sdist bdist_wheel
	twine upload $(wildcard dist/celery-*$(VERSION)*) $(wildcard dist/celery_*$(VERSION)*)

docs:
		$(MAKE) -C docs/ html

test: unittests

unittests:
	python -m unittest discover tests

clean:
	rm -f dist/*
	rm -rf docs/_build docs/_static docs/_templates
