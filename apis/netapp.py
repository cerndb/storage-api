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

from flask_restplus import Namespace, Resource, fields, marshal

import apis

VOLUME_NAME_DESCRIPTION = ("The name of the volume. "
                           "Must not contain leading /")

api = Namespace('netapp',
                description='Operations on NetApp filers')

volume = api.model('Volume', {
    'name': fields.String(min_length=1,
                          description=VOLUME_NAME_DESCRIPTION,
                          example="foo/bar/baz",
                          required=True),
    'autosize_enabled': fields.Boolean(required=True,
                                       attribute='autosizeEnabled'),
    'size_used': fields.Integer(required=True,
                                attribute='sizeUsed'),
    'autosize_increment': fields.Integer(required=True,
                                         attribute="autosizeIncrement"),
    'state': fields.String(min_length=1, required=True),
    'size_total': fields.Integer(required=True,
                                 attribute="sizeTotal"),
    'max_autosize': fields.Integer(required=True,
                                   attribute="maxAutosize"),
    'filer_address': fields.String(min_length=1, required=True,
                                   attribute="filerAddress"),
    'junction_path': fields.String(min_length=1, required=True,
                                   attribute="junctionPath"),
    })

lock_model = api.model('Lock', {
    'host': fields.String(min_length=1, required=True,
                          example="dbthing.cern.ch")
})

access_model = api.model('Access', {
    'policy_name': fields.String(min_length=1,
                                 attribute="policyName"),
    'rules': fields.List(fields.String())
    })

access_rule_model = api.model('AccessRuleModel',
                              {'ruleState': fields.Boolean(description="The state of the given rule: true = accept, false otherwise",
                                                           required=True)})


optional_from_snapshot = api.model('OptionalFromSnapshot',
                                   {'from_snapshot':
                                    fields.String(min_length=1,
                                                  required=False,
                                                  description="The snapshot name to create/restore to",
                                                  attribute='from_snapshot')})


@api.route('/volumes/')
class AllVolumes(Resource):
    @api.doc(description="Get a list of all volumes",
             id='get_volumes')
    @api.marshal_with(volume, as_list=True)
    def get(self):
        return []


@api.route('/volumes/<path:volume_name>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class Volume(Resource):

    @api.marshal_with(volume, description="The volume named volume_name")
    @api.doc(description="Get a specific volume by name")
    @api.response(404, description="No such volume exists")
    def get(self, volume_name):
        return {}

    @api.doc(body=optional_from_snapshot)
    @api.expect(optional_from_snapshot, validate=True)
    def put(self, volume_name):
        return marshal(apis.api.payload, optional_from_snapshot)

    @api.doc(description=("Restrict the volume named *volume_name*"
                          "but do not actually delete it"),
             security='sso')
    @api.response(204, description="Successfully restricted",
                  model=None)
    @api.response(403, description="Unauthorised",
                  model=None)
    def delete(self, volume_name):
        return {}

    @api.doc(description="Partially update volume_name",
             security='sso')
    @api.response(403, description="Unauthorised",
                  model=None)
    def patch(self, volume_name):
        return {}


@api.route('/volumes/<path:volume_name>/snapshots')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class AllSnapshots(Resource):
    def get(self, volume_name):
        return volume_name


@api.route('/volumes/<path:volume_name>/snapshots/<string:snapshot_name>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class Snapshots(Resource):
    def get(self):
        pass

    def put(self):
        pass

    def delete(self):
        pass


@api.route('/volumes/<path:volume_name>/locks')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.doc(description="Get the full set of locks")
class AllLocks(Resource):
    @api.marshal_with(lock_model, as_list=True,
                      description="The list of lock-holders for the volume")
    def get(self):
        pass


@api.route('/volumes/<path:volume_name>/locks/<string:host>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('host', "the host holding the lock in question")
class Locks(Resource):
    @api.doc(description="Lock the volume with host holding the lock",
             security='sso')
    @api.response(201, "A new lock was added")
    def put(self, lock_host):
        pass

    @api.doc(description="Force the lock for the host",
             security="sso")
    @api.response(403, description="Unauthorized")
    @api.response(204, description="Lock successfully forced")
    def delete(self, lock_host):
        pass


@api.route('/volumes/<path:volume_name>/access')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class AllAccess(Resource):
    @api.marshal_with(access_model,
                      description="The current ACL for the given volume",
                      as_list=True)
    @api.doc(description="Get the full ACL for the volume")
    def get(self):
        pass


@api.route('/volumes/<path:volume_name>/access/<string:rule>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('rule', "The rule to operate on. Must match a rule in the ACL exactly (literally)")
class Access(Resource):

    @api.doc(description="Get the access status of a given rule")
    @api.response(404, description="No such rule exists")
    @api.marshal_with(access_rule_model, description="The status of rule")
    def get(self):
        pass

    @api.doc(description="Grant hosts matching a given pattern access to the given volume")
    @api.response(201, description="A new access rule was added")
    def put(self):
        pass

    @api.doc(description=("Revoke the access for a given rule in the ACL."))
    @api.response(204, description="Successfully revoked the access for the given rule")
    @api.response(404, description="No such rule exists")
    def delete(self):
        pass
