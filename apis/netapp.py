# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

"""
This module covers the API for the NetApp filers.
"""

from flask_restplus import Namespace, Resource, fields

api = Namespace('netapp', description='Operations on NetApp filers')

volume = api.model('Volume', {
    'name': fields.String,
    'autosize_enabled': fields.Boolean,
    'size_used': fields.Integer,
    'autosize_increment': fields.Integer,
    'state': fields.String,
    'size_total': fields.Integer,
    'max_autosize': fields.Integer,
    'filer_address': fields.String,
    'junction_path': fields.String,
    })


@api.route('/volumes/')
class AllVolumes(Resource):

    @api.marshal_with(volume, as_list=True)
    def get(self):
        return []


@api.route('/volumes/<string:volume_name>')
class Volume(Resource):

    @api.marshal_with(volume)
    def get(self, volume_name):
        return {}

    def put(self, volume_name):
        return {}

    def delete(self, volume_name):
        return {}

    def patch(self, volume_name):
        return {}


@api.route('/volumes/<string:volume_name>/snapshots')
class AllSnapshots(Resource):
    def get(self):
        pass


@api.route('/volumes/<string:volume_name>/snapshots/<string:snapshot_name>')
class Snapshots(Resource):
    def get(self):
        pass

    def put(self):
        pass

    def delete(self):
        pass


@api.route('/volumes/<string:volume_name>/locks')
class AllLocks(Resource):
    def get(self):
        pass


@api.route('/volumes/<string:volume_name>/locks/<string:host>')
class Locks(Resource):
    def get(self, lock_host):
        pass

    def put(self, lock_host):
        pass

    def delete(self, lock_host):
        pass


@api.route('/volumes/<string:volume_name>/access')
class AllAccess(Resource):
    def get(self):
        pass


@api.route('/volumes/<string:volume_name>/access/<string:rule>')
class Access(Resource):
    def get(self):
        pass

    def put(self):
        pass

    def delete(self):
        pass
