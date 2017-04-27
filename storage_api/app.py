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

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

api.init_app(app)

oauth = OAuth(app)
oauth_client_id = os.getenv('OAUTH_CLIENT_ID', 'dummy_id')
oauth_secret_key = os.getenv('OAUTH_SECRET_KEY', 'dummy_key')
oauth_access_token_url = os.getenv('OAUTH_TOKEN_URL',
                                   'https://oauth.web.cern.ch/OAuth/Token')
oauth_authorze_url = os.getenv('OAUTH_AUTHORIZE_URL',
                               'https://oauth.web.cern.ch/OAuth/Authorize')
oauth_groups_url = os.getenv('OAUTH_GROUPS_URL',
                             'https://oauthresource.web.cern.ch/api/Groups')
oauth_callback_url_relative = os.getenv('OAUTH_CALLBACK_URL_RELATIVE',
                                        '/oauth-done')

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
               for k, v in os.environ.items() if k[:5] == "OAUTH"])))

try:
    netapp_host = os.environ['ONTAP_HOST']
    netapp_username = os.environ['ONTAP_USERNAME']
    netapp_password = os.environ['ONTAP_PASSWORD']
    netapp_vserver = os.environ['ONTAP_VSERVER']
    server = netapp.api.Server(hostname=netapp_host,
                               username=netapp_username,
                               password=netapp_password,
                               vserver=netapp_vserver)
    extensions.NetappStorage(netapp_server=server).init_app(app)
    log.info("Set up NetApp backend")
except KeyError:
    log.error("NetApp environment variables not configured, back-end inactive")
    pass

extensions.DummyStorage().init_app(app)


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
                    .format(", ".join(groups)))
    flask.session['user']["group"] = groups
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
