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


SOURCES:=$(shell find storage_api -name "*.py")
VERSION:=$(shell grep "__version__ =" storage_api/apis/__init__.py | sed "s|.*= '\(.*\)'|\1|")

clean:
	find . -name \*.pyc -o -name \*.pyo -o -name __pycache__ -exec rm -rf {} +
	rm -f $(TARFILE)
	make stop
	rm -rf swagger.json html
	cd doc && make clean
lint: $(SOURCES)
	flake8 $(SOURCES)
	 # mypy --ignore-missing-imports  \
	 #       --check-untyped-defs --warn-no-return \
	 #       $(SOURCES)

.PHONY: lint

devserver.PID:
	FLASK_APP=storage_api.app FLASK_DEBUG=true flask run & echo $$! > $@;


devserver: devserver.PID


stop: devserver.PID
	kill `cat $<` && rm $<


test: $(SOURCES)
	pytest -vvv --runslow --hypothesis-profile=ci
.PHONY: test


swagger.json: $(SOURCES) devserver.PID
	sleep 2 && wget http://127.0.0.1:5000/swagger.json -O swagger.json
	make stop

doc/source/modules.rst: Makefile $(SOURCES)
	sphinx-apidoc -f -o doc/source/ . setup.py extensions/tests tests conftest.py

html: swagger.json doc/source/modules.rst
	cd doc && make html
	mkdir -p html/api
	cp -r doc/_build/html/* html/
	spectacle --target-dir html/api swagger.json

doc_deploy: swagger.json html
	bash ./deploy.sh html
.PHONY: doc_deploy

image:
	docker build -t  "gitlab-registry.cern.ch/db/storage-api:runner" -t "gitlab-registry.cern.ch/db/storage-api:$(VERSION)" .

push-image:
	docker push "gitlab-registry.cern.ch/db/storage-api:runner"
	docker push "gitlab-registry.cern.ch/db/storage-api:$(VERSION)"

deploy-os-prod:
	oc import-image --token ${OPENSHIFT_PUSH_TOKEN_PROD} --namespace it-db-storage-api --server "https://openshift.cern.ch" "db/storage-api:runner"

deploy-os-dev:
	oc tag --token ${OPENSHIFT_PUSH_TOKEN_DEV} --namespace it-db-storage-api-dev --server "https://openshift.cern.ch" --source=docker "gitlab-registry.cern.ch/db/storage-api:$(VERSION)" "db/storage-api-dev:$(VERSION)"
	oc import-image --token ${OPENSHIFT_PUSH_TOKEN_DEV} --namespace it-db-storage-api-dev --server "https://openshift.cern.ch" "db/storage-api-dev:$(VERSION)"

run:
	docker run -it --rm --publish=8000:8000 \
	-e SAPI_BACKENDS=dummy🌈DummyStorage \
	-e SAPI_OAUTH_CLIENT_ID=blergh \
	-e SAPI_OAUTH_SECRET_KEY=bork \
	-e FLASK_APP=storage_api.app \
	-e FLASK_DEBUG=true "gitlab-registry.cern.ch/db/storage-api:runner"

push_version:
	make test
	git push origin :refs/tags/${VERSION}
	git tag -f ${VERSION}
	git push --tags
