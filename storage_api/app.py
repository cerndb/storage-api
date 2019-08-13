#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from storage_api import conf
from storage_api.apis import api
from storage_api.apis.common import auth
import storage_api.extensions as extensions

import os

from flask import Flask

app = Flask(__name__)
app.secret_key = os.urandom(24)

api.init_app(app)
conf.load_basic_auth_conf(app)
conf.load_oauth_conf(app)
conf.load_backend_conf(app, backends_module=extensions)
auth.setup_roles_from_env(app)
auth.setup_basic_auth(app)
auth.setup_oauth(app,
                 login_endpoint=auth.authorizations['sso']['authorizationUrl'],
                 logout_endpoint="/logout")


if __name__ == '__main__':
    app.run(debug=True)
