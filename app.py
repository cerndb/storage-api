#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.
from apis import api
import apis
import extensions

import os
import logging

import flask
from flask import Flask
from flask_sso import SSO

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

api.init_app(app)

SSO_ATTRIBUTE_MAP = {
    'ADFS_LOGIN': (True, 'username'),
    'ADFS_FULLNAME': (True, 'fullname'),
    'ADFS_PERSONID': (True, 'personid'),
    'ADFS_DEPARTMENT': (True, 'department'),
    'ADFS_EMAIL': (True, 'email'),
    'ADFS_GROUP': (True, 'group')
}

app.config.setdefault('SSO_ATTRIBUTE_MAP', SSO_ATTRIBUTE_MAP)
app.config.setdefault('SSO_LOGIN_URL', '/login')

sso = SSO(app=app)
app.secret_key = os.urandom(24)

extensions.DummyStorage().init_app(app)


@sso.login_handler
def login(user_info):   # pragma: no cover
    flask.session['user'] = user_info
    groups = user_info["group"].split(';')
    app.logger.info("Shibboleth reported the following groups: {}"
                    .format(", ".join(groups)))
    flask.session['user']["group"] = groups
    return flask.redirect('/')


@sso.login_error_handler
def error_callback(user_info):   # pragma: no cover
    if not app.debug:
        return flask.abort(403)
    else:
        app.logger.warning("Failed login, but authenticating anyway as"
                           " we are in dev mode")
        flask.session['user'] = user_info
        flask.session['user']['group'] = [apis.common.ADMIN_GROUP]
        app.logger.info("User data is: {}".format(str(flask.session['user'])))
        return flask.redirect('/')


@app.route('/logout')
def logout():   # pragma: no cover
    app.logger.info("Current session data: {}".format(str(flask.session)))
    if 'user' in flask.session:
        app.logger.info("Logging out user")
        flask.session.pop('user')
    else:
        app.logger.warning("No user logged in!")

    return flask.redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
