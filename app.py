#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.


from flask import Flask
from apis import api

app = Flask(__name__)
api.init_app(app)

if __name__ == '__main__':
    app.run(debug=True)
