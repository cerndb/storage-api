# CERN Unified Storage API

[![Build Status](https://travis-ci.org/cerndb/storage-api.svg?branch=master)](https://travis-ci.org/cerndb/storage-api)
[![Coverage Status](https://coveralls.io/repos/github/cerndb/storage-api/badge.svg?branch=master)](https://coveralls.io/github/cerndb/storage-api?branch=master)

## Aim of the project

IT DB Storage team is facing the need to work with different storage
providers in order to deliver different storage solutions that should
adapt to different projects needs. So far, a library and a set of
scripts has been developed to interact mainly with NetApp storage.  The
actual solution presents a RESTful API developed using Flask and
Python 3.

## Components and Design

The Storage API uses the flask-sso module developed by
[Invenio](https://github.com/inveniosoftware/flask-sso). Authorisation
is based on CERN e-groups (Active Directory distribution lists) and it's
implemented on the endpoint using a decorator. Authentication together
with some basic access control is based on
[Shibboleth](https://shibboleth.net/) implementing Single Sign On
(SSO). The use of Shibboleth determined the choice of an http server to
Apache. An again the use of Apache somehow made natural to use mod_wsgi
as WSGI platform to run python code.

The application is designed around common Python and Flask framework
patterns, with some help from the flask-restplus framework to provide
boilerplate REST code. A factory pattern is used to mount the same APIs
mapped to different back-ends as Flask paths. Back-ends are implemented
as Flask extensions and modelled using an
[abstract base class](https://pymotw.com/2/abc/), and resolved at
run-time. This way, the API allows for successive implementations of
future back-ends on the same API.

## Development

Development and testing (without proper authentication) can be done
without a full deployment setup (see below). You need Python 3 and
virtualenv (on Ubuntu `python3-virtualenv`) installed before running the
commands below.

```
git clone https://github.com/cerndb/storage-api
cd storage-api
virtualenv --python=python3 v1
source .v1/bin/activate
pip install -r requirements.txt
```

You can run the API in the Flask development server without SSO like this:

```
$ export FLASK_APP=app.py
$ export FLASK_DEBUG=1
$ flask run
```

Accessing `/login` in debug mode *will immediately authorise you*.

There is also a shorthand Makefile option available as `make devserver`
with corresponding `make stop`.

### Configuration

Configuration is done using environment variables, as per the 12-factor
app pattern. The following environment variables are used:

- `SAPI_OAUTH_CLIENT_ID`: The public client ID for the OAuth2 service
  the storage API runs as
- `SAPI_OAUTH_SECRET_KEY`: The private key of the OAuth2 service the
  storage API runs as
- `SAPI_ROLE_USER_GROUPS`: A comma-separated list of groups whose users
  are just plain users. If the list is empty or unset, unauthenticated
  users are included in the user role and given access to certain
  (non-destructive) endpoints. See the API documentation!
- `SAPI_ROLE_ADMIN_GROUPS`: A comma-separated list of groups whose users
  are (at least) administrators. Empty list or unset variable means
  the role is disabled.
- `SAPI_ROLE_UBER_ADMIN_GROUPS`: A comma-separated list of groups whose
  users are uber-admins (e.g. the highest privilege level).
- `SAPI_BACKENDS`: A unicorn emoji-separated list of back-ends to enable,
  and their configuration as per the following pattern:
  `endpoint_name:BackEndClass:option_name:option_value:another_option_name:another_option_value`,
  where endpoint_name is the part that goes into the
  `/<endpoint_name>/volumes>` part of the URL, `BackEndClass` is the
  name of a class that implements the corresponding back-end
  (e.g. `DummyStorage`), and the following set of key emoji-separated
  options will be passed as keys and value arguments to that back-ends
  constructor.

  The following example sets up a NetApp back-end and RAM-backed dummy back-end:
`export SAPI_BACKENDS="dummy🔑DummyStorage🦄netapp🔑NetappStorage🔑username🔑storage-api🔑password🔑myPassword:@;🔑vserver🔑vs3sx50"`

  Please note that it is perfectly possible to set up multiple endpoints with the same back-end.

## Testing and Continuous Integration

Continuous integration is provided by Travis, and tests are run using
py.test and the Hypothesis framework. A more exhaustive Hypothesis test
run takes a while to run (around 10-15 minutes), so it is advised to use
the much less exhaustive "dev" test profile and leave the "ci" profile
for Travis. The profile can be provided as a command-line option for
pytest: `pytest --hypothesis-profile=dev`. Logging verbosity during
tests can be increased using `-vvvv` with a variable number of `v`:s
(more is noisier).

## Deployment

The API is deployed via an RPM, which sets up a clean Python virtual
environment and installs using normal Pip proceducers into it (e.g. the
same as the ones used for development). An example config for Apache
featuring SSO/Shibboleth config and proper virtual environment handling
is available in `templates/storage-api.conf`. For more information, see
[the mod_wsgi documentation on the subject][mod-wsgi-venv].

To combine https access with Single Sign On a Shibboleth &
Apache setup is required. The setup steps are quite well described by
[Alex Pearce article][ap-flask-sso],
especially targeting a CERN environment.

## Documentation

An interactive API Documentation is automatically generated by
flask-restplus and served at the path `/`, with a JSON description
available at `/swagger.json`. A HTML version is also rendered by
[Spectacle](http://sourcey.com/spectacle/) and published automatically
by Travis to
[cerndb.github.io/storage-api](http://cerndb.github.io/storage-api/).


[mod-wsgi-venv]: http://modwsgi.readthedocs.io/en/develop/user-guides/virtual-environments.html
[ap-flask-sso]: https://alexpearce.me/2014/10/setting-up-flask-with-apache-and-shibboleth/
