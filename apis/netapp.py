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
import apis

from flask_restplus import Namespace, Resource, fields, marshal, abort

VOLUME_NAME_DESCRIPTION = ("The name of the volume. "
                           "Must not contain leading /")
api = Namespace('netapp',
                description='Operations on NetApp filers')

volume_writable_model = api.model('VolumeWritable', {
    'autosize_enabled': fields.Boolean(attribute='autosizeEnabled'),
    'autosize_increment': fields.Integer(attribute="autosizeIncrement"),
    'max_autosize': fields.Integer(attribute="maxAutosize"),
    })

volume = api.inherit('Volume', volume_writable_model, {
    'name': fields.String(min_length=1,
                          description=VOLUME_NAME_DESCRIPTION,
                          example="foo/bar/baz",
                          ),
    'size_used': fields.Integer(attribute='sizeUsed'),
    'state': fields.String(min_length=1, ),
    'size_total': fields.Integer(attribute="sizeTotal"),
    'filer_address': fields.String(min_length=1,
                                   attribute="filerAddress"),
    'junction_path': fields.String(min_length=1,
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
                              {'rule_state':
                               fields.Boolean(
                                   description=(
                                       "The state of the given rule: "
                                       "true = accept, false otherwise"),
                                   required=True)})

snapshot_model = api.model('Snapshot', {
    'name': fields.Boolean(),
    'autosize_enabled': fields.Boolean(attribute='autosizeEnabled'),
    'autosize_increment': fields.Integer(attribute="autosizeIncrement"),
    'max_autosize': fields.Integer(attribute="maxAutosize"),
    })

optional_from_snapshot = api.inherit(
    'OptionalFromSnapshot',
    snapshot_model,
    {
        'from_snapshot':
        fields.String(
            min_length=1,
            required=False,
            description=("The snapshot name "
                         "to create/restore to"),
            attribute='fromSnapshot')})

snapshot_put_model = api.model('SnapshotPut', {
    'purge_old_if_needed': fields.Boolean(
        description=("If `true`, purge the oldest snapshot iff necessary "
                     " to create a new one"))})


@api.route('/volumes/')
class AllVolumes(Resource):
    @api.doc(description="Get a list of all volumes",
             id='get_volumes')
    @api.marshal_with(volume, as_list=True)
    def get(self):
        abort(500, "Would return a list of all volumes")


@api.route('/volumes/<path:volume_name>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class Volume(Resource):

    @api.marshal_with(volume, description="The volume named volume_name")
    @api.doc(description="Get a specific volume by name")
    @api.response(404, description="No such volume exists")
    def get(self, volume_name):
        abort(500, "Would return a volume")

    @api.doc(body=optional_from_snapshot)
    @api.expect(optional_from_snapshot, validate=True)
    def put(self, volume_name):
        return

    @api.doc(description=("Restrict the volume named *volume_name*"
                          " but do not actually delete it"),
             security='sso')
    @api.response(204, description="Successfully restricted",
                  model=None)
    @api.response(403, description="Unauthorised",
                  model=None)
    def delete(self, volume_name):
        abort(500, "Would restrict '{}'".format(volume_name))

    @api.doc(description="Partially update volume_name",
             security='sso')
    @api.response(403, description="Unauthorised",
                  model=None)
    @api.expect(volume_writable_model, validate=True)
    def patch(self, volume_name):
        data = marshal(apis.api.payload, volume_writable_model)
        abort(500, ("Would update with values '{}'"
                    .format(dict(data))))


@api.route('/volumes/<path:volume_name>/snapshots')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class AllSnapshots(Resource):
    @api.marshal_with(snapshot_model, description="All snapshots for the volume",
                      as_list=True)
    def get(self, volume_name):
        return volume_name


@api.route('/volumes/<path:volume_name>/snapshots/<string:snapshot_name>')
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class Snapshots(Resource):

    @api.doc(description="Get the current information for a given snapshot")
    @api.marshal_with(snapshot_model)
    def get(self):
        pass

    @api.response(409, description=("Too many snapshots, cannot create another. "
                                    "Try `purge_old_if_needed=true`."))
    @api.response(403, description="Insufficient rights/not logged in")
    @api.response(201, description="Successfully created a snapshot")
    @api.expect(snapshot_put_model)
    @api.doc(description=("Create a new snapshot of *volume_name*"
                          " under *snapshot_name*"))
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
