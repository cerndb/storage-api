#*******************************************************************************
# Copyright (C) 2015, CERN
# # This software is distributed under the terms of the GNU General Public
# # License version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# # In applying this license, CERN does not waive the privileges and immunities
# # granted to it by virtue of its status as Intergovernmental Organization
# # or submit itself to any jurisdiction.
# #
# #
# #*******************************************************************************
SPECFILE=storage-api.spec
REPOURL=git+https://github.com
# DB gitlab group
REPOPREFIX=/cerndb
REPO_NAME=storage-api
SOURCES := $(shell find apis app.py -name '*.py')

# Get all the package infos from the spec file
PKGVERSION=$(shell awk '/Version:/ { print $$2 }' ${SPECFILE})
PKGRELEASE=$(shell awk '/Release:/ { print $$2 }' ${SPECFILE} | sed -e 's/\%{?dist}//')
PKGNAME=$(shell awk '/Name:/ { print $$2 }' ${SPECFILE})
PKGID=$(PKGNAME)-$(PKGVERSION)
TARFILE=$(PKGID).tar.gz

sources:
	rm -rf /tmp/$(PKGID)
	mkdir /tmp/$(PKGID)
	cp -rv * /tmp/$(PKGID)/ > /dev/null 2>&1
	pwd ; ls -l
	cd /tmp ; tar --exclude .svn --exclude .git --exclude .gitkeep -czf $(TARFILE) $(PKGID)
	mv /tmp/$(TARFILE) .
	rm -rf /tmp/$(PKGID)

all:    sources

clean:
	find . -name \*.pyc -o -name \*.pyo -o -name __pycache__ -exec rm -rf {} +
	rm -f $(TARFILE)
	make stop
	rm -rf swagger.json html
	cd doc && make clean

srpm:   all
	rpmbuild -bs --define '_sourcedir $(PWD)' ${SPECFILE}

rpm:    all
	rpmbuild -ba --define '_sourcedir $(PWD)' ${SPECFILE}

scratch:
	koji build db6 --nowait --scratch  ${REPOURL}${REPOPREFIX}/${REPO_NAME}.git#master
	koji build db7 --nowait --scratch  ${REPOURL}${REPOPREFIX}/${REPO_NAME}.git#master

build:
	koji build db6 --nowait ${REPOURL}${REPOPREFIX}/${REPO_NAME}.git#master
	koji build db7 --nowait ${REPOURL}${REPOPREFIX}/${REPO_NAME}.git#master

tag-qa:
	koji tag-build db6-qa $(PKGID)-$(PKGRELEASE).el6
	koji tag-build db7-qa $(PKGID)-$(PKGRELEASE).el7.cern

tag-stable:
	koji tag-build db6-stable $(PKGID)-$(PKGRELEASE).el6
	koji tag-build db7-stable $(PKGID)-$(PKGRELEASE).el7.cern

lint: $(SOURCES)
	flake8 app.py apis setup.py extensions
	mypy --ignore-missing-imports --fast-parser \
	     --check-untyped-defs --warn-no-return \
	     app.py apis setup.py extensions

.PHONY: lint

devserver.PID:
	FLASK_APP=app.py FLASK_DEBUG=true flask run & echo $$! > $@;


devserver: devserver.PID


stop: devserver.PID
	kill `cat $<` && rm $<


test: $(SOURCES)
	pytest -vvv --runslow --hypothesis-profile=ci
.PHONY: test


swagger.json: $(SOURCES) devserver.PID
	sleep 2 && wget http://127.0.0.1:5000/swagger.json -O swagger.json
	make stop

doc/source/modules.rst:
	sphinx-apidoc -f -o doc/source/ .

html: swagger.json doc/source/modules.rst
	cd doc && make html
	mkdir -p html/api
	cp -r doc/_build/html/* html/
	spectacle --target-dir html/api swagger.json

doc_deploy: swagger.json html
	bash ./deploy.sh html
.PHONY: doc_deploy
