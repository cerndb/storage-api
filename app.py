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

from flask import Flask, redirect, abort, session
from flask_sso import SSO

app = Flask(__name__)
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
def login(user_info):
    session['user'] = user_info
    session['user']["group"] = user_info["group"].split(';')
    return redirect('/')


@sso.login_error_handler
def error_callback(user_info):
    if not app.debug:
        return abort(403)
    else:
        session['user'] = user_info
        session['user']['group'] = [apis.common.ADMIN_GROUP]
        print(user_info)
        return redirect('/')


@app.route('/logout')
def logout():
    session.pop('user')
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
