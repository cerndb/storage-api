# CERN Unified Storage API

[![build status](https://gitlab.cern.ch/db/storage-api/badges/master/build.svg)](https://gitlab.cern.ch/db/storage-api/commits/master)
[![coverage report](https://gitlab.cern.ch/db/storage-api/badges/master/coverage.svg)](https://gitlab.cern.ch/db/storage-api/commits/master)

## Aim of the project

IT DB Storage team is facing the need to work with different storage
providers in order to deliver different storage solutions that should
adapt to different projects needs. So far, a library and a set of
scripts has been developed to interact mainly with NetApp storage.  The
actual solution presents a RESTful API developed using Flask and
Python 3.

## Usage

Accessing `/login` will put you through the standard CERN single sign-on
process and return you to the API with an authenticated session once you
are done. For use in Python scripts and applications, setting the
relevant session cookies using
[cern-sso-python](https://gitlab.cern.ch/db/cern-sso-python) is
recommended.

For API documentation, see the generated Swagger documentation (linked below).

## Components and Design

Authorisation is based on CERN e-groups (Active Directory distribution
lists), and user authentication is done using the central OAuth2
providers.

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

Accessing `/login` in debug mode *will immediately authorise you as an
uber-admin*.

There is also a shorthand Makefile option available as `make devserver`
with corresponding `make stop`.

It is also possible to run the Dockerised image with `make image run`. 
Remember that you can determine which random port the container
was assigned with `docker port <name of container>`.

### Configuration

Configuration is done using environment variables, as per the 12-factor
app pattern. The following environment variables are used:

- `SAPI_OAUTH_CLIENT_ID`: The public client ID for the OAuth2 service
  the storage API runs as
- `SAPI_OAUTH_SECRET_KEY`: The private key of the OAuth2 service the
  storage API runs as

The following keys are optional:
- `SAPI_OAUTH_TOKEN_URL`: The URL to get OAuth2 Tokens from. **Default**:
  `https://oauth.web.cern.ch/OAuth/Token`
- `SAPI_OAUTH_AUTHORIZE_URL`: The URL to send OAuth2 Authorization
  requests to. **Default**: `https://oauth.web.cern.ch/OAuth/Authorize`
- `SAPI_OAUTH_GROUPS_URL`: The URL to send a GET request with the
  current OAuth2 token to receive a list of groups the current user is a
  member of. **Default**: `https://oauthresource.web.cern.ch/api/Groups`
- `SAPI_OAUTH_CALLBACK_URL_RELATIVE`: The relative (to the app's root)
  URL to report as the call-back URL to the OAuth2 Authorize server. You
  most likely do not need to change this, unless you have some really
  exotic routing pattern. **Default**: `/oauth-done`

The following configuration options control the role-based access control:
- `SAPI_ROLE_USER_GROUPS`: A comma-separated list of groups whose users
  are just plain users. If the list is empty or unset, unauthenticated
  users are included in the user role and given access to certain
  (non-destructive) endpoints. See the API documentation!
- `SAPI_ROLE_ADMIN_GROUPS`: A comma-separated list of groups whose users
  are (at least) administrators. Empty list or unset variable means
  the role is disabled.
- `SAPI_ROLE_UBER_ADMIN_GROUPS`: A comma-separated list of groups whose
  users are uber-admins. Empty list
  or unset variable means the role is disabled.

Please note that roles are distinct, e.g. the admin role is not
contained within the uber-admin-role. If you want both, you need to have
both.

Back-ends are configured using the following pattern:
- `SAPI_BACKENDS`: A unicorn emoji-separated (:unicorn:) list of back-ends to enable,
  and their configuration as per the following pattern:
  `endpoint_name:BackEndClass:option_name:option_value:another_option_name:another_option_value`,
  where endpoint_name is the part that goes into the
  `/<endpoint_name>/volumes>` part of the URL, `BackEndClass` is the
  name of a class that implements the corresponding back-end
  (e.g. `DummyStorage`), and the following set of rainbow emoji-separated
  options (:rainbow:) will be passed as keys and value arguments to that back-ends
  constructor.

  The following example sets up a NetApp back-end and RAM-backed dummy back-end:
`export SAPI_BACKENDS="dummy🌈DummyStorage🦄netapp🌈NetappStorage🌈username🌈storage-api🌈password🌈myPassword:@;🌈vserver🌈vs3sx50"`

  Please note that it is perfectly possible to set up multiple endpoints
  with the same back-end, e.g. multiple NetApp filers or clusters with
  different vservers on different endpoints. Endpoints needs to be
  unique though.
 
**Without at least one configured endpoint, the app will not run.**

## Testing and Continuous Integration

Continuous integration is provided by GitLab CI, and tests are run using
py.test and the Hypothesis framework. A more exhaustive Hypothesis test
run takes a while to run (around 10-15 minutes), so it is advised to use
the much less exhaustive "dev" test profile and leave the "ci" profile
for Travis. The profile can be provided as a command-line option for
pytest: `pytest --hypothesis-profile=dev`. Logging verbosity during
tests can be increased using `-vvvv` with a variable number of `v`:s
(more is noisier).

## Deployment

The API is deployed via a standard Docker container to OpenShift. It is
automatically built by the GitLab Continuous Integration system on
tagged releases; whenever a tag is pushed to the GitLab repository, a
corresponding Docker Image is built and tagged with the same
tag. Additionally, a template for OpenShift is available at
`storage-api-openshift-template`. During version releases, the template
will be pushed to both production and test environments automatically,
as the operation doesn't affect the currently running service.

OpenShift's HAProxy is set to a very long timeout for the route -- about
60 seconds (see the template), and the same goes for uwsgi's harakiri
setting. This is due to the fact that volume listings on big production
filers can take a long while to complete -- closer to a minute in a
worst-case scenario.

Whenever all the build steps have passed, images can be manually
deployed from the GitLab Pipeline to OpenShift using the jobs
`dev-deploy` and `prod-deploy` respectively.

To start a release, run `make push_version`, which will automatically
tag the current tree with the corresponding version (as extracted from
the source code), and commence the process.

## Documentation

An interactive API Documentation is automatically generated by
flask-restplus and served at the path `/`, with a JSON description
available at `/swagger.json`. A HTML version is also rendered by
[Spectacle](http://sourcey.com/spectacle/) and published automatically
by GihLab CI to
[https://db-storage-api-docs.web.cern.ch](https://db-storage-api-docs.web.cern.ch)
(only CERN-internal, unfortunately). A copy is also
[available at GitHub pages](http://cerndb.github.io/storage-api/).
