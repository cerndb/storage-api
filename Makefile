SOURCES := $(shell find apis app.py -name '*.py')

lint: $(SOURCES)
	flake8 app.py apis setup.py

.PHONY: lint


devserver:
	FLASK_APP=app.py FLASK_DEBUG=true flask run
.PHONY: devserver


test: $(SOURCES)
	pytest -vvv --runslow
.PHONY: test
