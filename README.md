# storage-api

[![Build Status](https://travis-ci.org/cerndb/storage-api.svg?branch=master)](https://travis-ci.org/cerndb/storage-api)

## Aim of the project

IT DB Storage team is facing the need to work with different storage providers in order to deliver different storage solutions that should adapt to different projects needs. So far, a library and a set of scripts has been developed to interact mainly with NetApp storage. 
The actual solution presents a RESTful API developed using Flask and Python3. Using the power of Python and its natural Object Oriented approach, storage api pretends to cover all possible use cases e.g. NetApp, Ceph,.. and different scenarios: operations and provisioning. 

## Components

The Storage-api uses the flask-sso module developed by [Invenio](https://github.com/inveniosoftware/flask-sso). Authorisation is based on CERN e-groups (Active Directory distribution lists) and it's implemented on the endpoint using a decorator. Authentication together with some basic access control is based on [Shibboleth](https://shibboleth.net/) implementing Single Sign On (SSO). The use of Shibboleth determined  the choice of an http server to Apache. An again the use of Apache somehow made natural to use mod_wsgi as WSGI platform to run python code.   

The API is deployed via an rpm and it runs in its own virtual environment. Further customization is done via Puppet. 
Configuration files are expected to be found under /etc/storage. Three files should be placed there:

* logging.conf: configuration of the python logging module. Files are expected to be found under /var/log/storage
* storage.conf: a definition of the different storage islands. Passwords are populated using Teigi puppet module. 
* storage-api.conf: this file it should be place under Apache /etc/httpd/conf.d directory and represents the configuration of shibboleth for the SSO and mod_wsgi (mod_wsgi should be compiled for Python3). mod_wsgi should be loaded into Apache http server e.g. in our httpd.conf: _LoadModule wsgi_module /usr/local/lib/python3.5/site-packages/mod_wsgi/server/mod_wsgi-py35.cpython-35m-x86_64-linux-gnu.so_).

A template for all three is provided under templates directory.

## Development

In order to further develope/test the core functionality no http server is needed. In order to test the http endpoints you can use the flask framework. To combine https access with Single Sign On a Shibboleth & Apache setup is required. The setup steps are quite well described by [Alex Pearce article](https://alexpearce.me/2014/10/setting-up-flask-with-apache-and-shibboleth/), especially targeting a CERN environment. 

```
git clone https://github.com/cerndb/storage-api
cd storage-api
virtualenv v1
source .v1/bin/activate
pip3 install -r requirements.txt
python3 setup.py install
```

## Example

In a CERN openstack workstation, our storage-api implementation is running on a server under storage-api:5002, it's shown here how to invoke the storage-api different endpoint from the command line using curl:

```
# Get the SSO cookie
cern-get-sso-cookie --krb -u https://storage-api.cern.ch:5002/login -o storage.api

# Create an snapshot called mysnap01 (in base64 'bXlzbmFwMDE=') for dbnasc501-c:/ORA/dbs00/VOLDEMO -> in base64 -> 'ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P'

curl  -i https://storage-api.cern.ch:5002/storage/api/v1.0/paths/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P -X POST  -d "snapname=bXlzbmFwMDE=" --cookie storage.api

# Create a clone from mysnap01

curl  -i https://storage-api.cern.ch:5002/storage/api/v1.0/paths/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P -X POST  -d "snapname=bXlzbmFwMDE=" -d "clone=1" --cookie storage.api

# Retrieve all snapshots from dbnasc501-c:/ORA/dbs00/VOLDEMO (no authentication required)

curl  -i https://storage-api.cern.ch:5002/storage/api/v1.0/paths/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P -X GET

# Retrieve all export rules that apply to dbnasc501:/ORA/dbs00/VOLDEMO file system

curl -i https://storage-api.cern.ch:5002/storage/api/v1.0/exports/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P -X GET

# Add a new IP (128.142.243.76 in base64 'MTI4LjE0Mi4yNDMuNzY=') to the export-police applied to dbnasc501:/ORA/dbs00/VOLDEMO file system

curl -i https://storage-api.cern.ch:5002/storage/api/v1.0/exports/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1P -X PUT -d "addrule=MTI4LjE0Mi4yNDMuNzY=" --cookie storage.api

# Destroy a clone: dbnasc501-c:/ORA/dbs00/VOLDEMO_05062016_151131

curl -i https://storage-api.cern.ch:5002/storage/api/v1.0/volumes/ZGJuYXNjNTAxLWM6L09SQS9kYnMwMC9WT0xERU1PXzA1MDYyMDE2XzE1MTEzMQ== -X DELETE -d "clone=1" --cookie storage.api

 
