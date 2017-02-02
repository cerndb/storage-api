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
