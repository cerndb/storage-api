#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from flask import Flask, request
from flask.ext.restful import Api, Resource
from storage.api.PathREST import PathREST
from storage.api.VolumeREST import VolumeREST
from storage.api.RulesREST import RulesREST

app = Flask(__name__)
api = Api(app)

		


api.add_resource(PathREST, '/storage/api/v1.0/paths/<string:path>')
api.add_resource(VolumeREST, '/storage/api/v1.0/volumes/<string:volname>')
api.add_resource(RulesREST, '/storage/api/v1.0/exports/<string:path>')

if __name__ == '__main__':
    app.run(debug=True)