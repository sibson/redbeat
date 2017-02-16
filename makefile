.PHONY: upload

version-%: OLDVERSION:=$(shell python setup.py --version)
version-%: 
	sed -i -e s/$(OLDVERSION)/$*/ setup.py
	git ci setup.py -m"bump version to $*"
	git tag -a v$* -m"release version $*"
	git push --tags


upload:
	python setup.py sdist
	twine upload dist/$(shell python setup.py --fullname).*
