SOURCES := $(shell find apis app.py -name '*.py')

lint: $(SOURCES)
	flake8 app.py apis setup.py

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

html: swagger.json
	mkdir -p html
	spectacle --target-dir html swagger.json

doc_deploy: swagger.json
	bash ./deploy.sh html

clean:
	rm -rf swagger.json html
	make stop
