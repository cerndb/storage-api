SOURCES := $(shell find apis app.py -name '*.py')

lint: $(SOURCES)
	flake8 app.py apis storage

.PHONY: lint
