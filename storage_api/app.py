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

import flask
from flask import Flask, url_for
from flask_oauthlib.client import OAuth
import netapp.api
from itertools import tee

# If you're not unicode ready, you're not ready, period.
BACKEND_SEPARATOR = "🦄"
CONFIG_SEPARATOR = "🌈"

app = Flask(__name__)
app.config['SUBSYSTEM'] = {}

logging.basicConfig(level=logging.DEBUG)


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
try:
    load_backend_conf(os.environ['SAPI_BACKENDS'])
except KeyError as e:
    log.error("You need to set $SAPI_BACKENDS!")


@app.route('/login')
def login():
    if app.debug:
        app.logger.warning("Failed login, but authenticating anyway as"
                           " we are in dev mode")
        flask.session['user'] = {}
        flask.session['user']['group'] = [apis.common.ADMIN_GROUP]
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
    groups = response['groups']
    flask.session['user'] = {}
    app.logger.info("OAuth reported the following groups: {}"
                    .format(", ".join(['"{}"'.format(g) for g in groups])))
    if apis.common.ADMIN_GROUP in groups:
        flask.session['user']["group"] = [apis.common.ADMIN_GROUP]
    else:
        app.logger.error("Group {} was not in the user's list!"
                         .format(apis.common.ADMIN_GROUP))
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
