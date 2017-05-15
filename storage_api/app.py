#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.
from storage_api.apis import api
import storage_api.apis as apis
import storage_api.extensions as extensions

import os
import logging
import csv
import io

import flask
from flask import Flask, url_for
from flask_oauthlib.client import OAuth
import netapp.api
from itertools import tee

# If you're not unicode ready, you're not ready, period.
BACKEND_SEPARATOR = "🦄"
CONFIG_SEPARATOR = "🌈"
USER_ROLES = ["USER", "ADMIN", "UBER_ADMIN"]

app = Flask(__name__)
app.config['SUBSYSTEM'] = {}
api.init_app(app)

oauth = OAuth(app)
oauth_client_id = os.getenv('SAPI_OAUTH_CLIENT_ID', 'dummy_id')
oauth_secret_key = os.getenv('SAPI_OAUTH_SECRET_KEY', 'dummy_key')
oauth_access_token_url = os.getenv('SAPI_OAUTH_TOKEN_URL',
                                   'https://oauth.web.cern.ch/OAuth/Token')
oauth_authorze_url = os.getenv('SAPI_OAUTH_AUTHORIZE_URL',
                               'https://oauth.web.cern.ch/OAuth/Authorize')
oauth_groups_url = os.getenv('SAPI_OAUTH_GROUPS_URL',
                             'https://oauthresource.web.cern.ch/api/Groups')
oauth_callback_url_relative = os.getenv('SAPI_OAUTH_CALLBACK_URL_RELATIVE',
                                        '/oauth-done')


def pairwise(iterable):
    return zip(iterable[0::2], iterable[1::2])


def conf_to_dict(conf_list):
    # If the length of the configuration is uneven, keys don't match up.
    assert len(conf_list) % 2 == 0
    return dict(pairwise(conf_list))


def load_backend_conf(conf):
    backends = conf.split(BACKEND_SEPARATOR)
    for backend_conf in backends:
        conf = backend_conf.split(CONFIG_SEPARATOR)
        endpoint = conf[0]

        # This is the class itself:
        Backend = getattr(extensions, conf[1])
        conf_dict = conf_to_dict(conf[2:])
        log.debug("Back-end conf dict: {}".format(conf_dict))
        backend = Backend(**conf_dict)
        backend.init_app(app, endpoint=endpoint)


def set_auth_string(role_name):
    role_name = role_name.upper()
    key_name = "{}_GROUPS".format(role_name)
    env_var_name = "SAPI_ROLE_{}_GROUPS".format(role_name)

    group_string = os.getenv(env_var_name, "")

    if not group_string:
        group_data = set()
    else:
        group_data = set(*csv.reader(io.StringIO(group_string),
                                     delimiter=","))
    app.config[key_name] = group_data


cern = oauth.remote_app(
    'cern',
    consumer_key=oauth_client_id,
    consumer_secret=oauth_secret_key,
    request_token_url=None,
    access_token_method='POST',
    access_token_url=oauth_access_token_url,
    authorize_url=oauth_authorze_url,
)

app.secret_key = os.urandom(24)
log = logging.getLogger(__name__)

log.debug("Set variables:\n{}".format(
    "\n".join(["{} = {}".format(k, v)
               for k, v in os.environ.items() if k[:4] == "SAPI"])))

log.info("Loading back-end conf from $SAPI_BACKENDS")
load_backend_conf(os.environ['SAPI_BACKENDS'])

log.info("Loading authorisation config")
[set_auth_string(role) for role in USER_ROLES]
if not app.config['USER_GROUPS']:
    app.config['USER_IS_UNAUTHENTICATED'] = True
else:
    app.config['USER_IS_UNAUTHENTICATED'] = False

@app.route('/login')
def login():
    if app.debug:
        app.logger.warning("Failed login, but authenticating anyway as"
                           " we are in dev mode")
        flask.session['user'] = {}
        flask.session['user']['roles'] = [apis.common.USER_ROLE,
                                          apis.common.ADMIN_ROLE,
                                          apis.common.UBER_ADMIN_ROLE]
        return flask.redirect('/')

    return cern.authorize(callback=url_for('authorized', _external=True))


@app.route(oauth_callback_url_relative)
def authorized():   # pragma: no cover
    resp = cern.authorized_response()
    if resp is None or resp.get('access_token') is None:
        return 'Access denied: reason=%s error=%s resp=%s' % (
            flask.request.args['error'],
            flask.request.args['error_description'],
            resp
        )
    flask.session['cern_token'] = (resp['access_token'], '')
    app.logger.info("Got authentication call-back from OAuth."
                    " Proceeding to fetch groups...")

    response = cern.get(oauth_groups_url).data
    user_groups = set(response['groups'])
    flask.session['user'] = {}
    session_roles = []
    app.logger.debug("OAuth reported the following groups: {}"
                     .format(", ".join(['"{}"'.format(g) for g in user_groups])))
    if not app.config['USER_GROUPS']:
        app.logger.info("No user groups configured, setting role USER")
        session_roles.append(apis.common.USER_ROLE)
    for role in USER_ROLES:
        overlap = user_groups.intersection(app.config['{}_GROUPS'
                                                      .format(role)])
        if overlap:
            app.logger.info("User was in {} role groups {}, granting role"
                            .format(role, ", ".join(overlap)))
            session_roles.append(getattr(apis.common, '{}_ROLE'.format(role)))
        else:
            app.logger.info("User was not in any {} role groups, denying"
                            .format(role))
    app.logger.info("Setting user roles: {}".format(", ".join(session_roles)))
    flask.session['user']['roles'] = session_roles
    return flask.redirect('/')


@app.route('/logout')
def logout():   # pragma: no cover
    app.logger.info("Current session data: {}".format(str(flask.session)))
    flask.session.pop('cern_token', None)
    flask.session.pop('user', None)
    return flask.redirect('/')


@cern.tokengetter
def get_cern_oauth_token():
    return flask.session.get('cern_token')


if __name__ == '__main__':
    app.run(debug=True)
