FROM python:3.6-alpine
MAINTAINER albin.stjerna@cern.ch
EXPOSE 8000

RUN apk add --update --no-cache gcc make musl-dev python3-dev linux-headers git libxslt-dev libxml2-dev

RUN pip3 install --upgrade pip
RUN pip3 install virtualenv uwsgi

RUN mkdir -p /opt/apps/storage-api/
COPY . /opt/apps/storage-api/
WORKDIR /opt/apps/storage-api
RUN adduser -D appserver
RUN chown -R appserver .
USER appserver

RUN virtualenv --python=python3 venv
RUN source venv/bin/activate && pip install -r requirements.txt
RUN source venv/bin/activate && python setup.py install
RUN source venv/bin/activate && pytest -vvv --ignore=venv
CMD uwsgi uwsgi.ini
