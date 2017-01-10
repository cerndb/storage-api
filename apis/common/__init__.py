#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import apis

from flask_restplus import Resource, fields, marshal, abort
from flask import current_app


VOLUME_NAME_DESCRIPTION = ("The name of the volume. "
                           "Must not contain leading /")


def dict_without(d, *keys):
    """
    Return a dictionary d, ensuring that keys are absent.
    """
    d2 = d.copy()
    for key in keys:
        d2.pop(key)

    return d2



def init_namespace(api, backend_name):
    def backend():
        return current_app.extensions[backend_name]

    volume_writable_model = api.model('VolumeWritable', {
        'autosize_enabled': fields.Boolean(),
        'autosize_increment': fields.Integer(),
        'max_autosize': fields.Integer(),
        })

    volume = api.inherit('Volume', volume_writable_model, {
        'name': fields.String(min_length=1,
                              description=VOLUME_NAME_DESCRIPTION,
                              example="foo/bar/baz",
                              ),
        'size_used': fields.Integer(),
        'state': fields.String(min_length=1, ),
        'size_total': fields.Integer(),
        'filer_address': fields.String(min_length=1),
        'junction_path': fields.String(min_length=1),
        })

    lock_model = api.model('Lock', {
        'host': fields.String(min_length=1, required=True,
                              example="dbthing.cern.ch")
    })

    access_model = api.model('Access', {
        'policy_name': fields.String(min_length=1),
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
        'name': fields.String(),
        'autosize_enabled': fields.Boolean(),
        'autosize_increment': fields.Integer(),
        'max_autosize': fields.Integer(),
        })

    optional_from_snapshot = api.inherit(
        'OptionalFromSnapshot',
        snapshot_model,
        {
            'from_snapshot':
            fields.String(
                required=False,
                description=("The snapshot name to create from/restore")),
            'from_volume':
            fields.String(required=False,
                          description=("When cloning a volume, use this volume"
                                       " as basis for the snapshot to start"
                                       " from"))})

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
            return backend().volumes


    @api.route('/volumes/<path:volume_name>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    class Volume(Resource):

        @api.marshal_with(volume, description="The volume named volume_name")
        @api.doc(description="Get a specific volume by name")
        @api.response(404, description="No such volume exists")
        def get(self, volume_name):
            try:
                return backend().get_volume(volume_name)
            except KeyError:
                abort(404, "No such volume: '{}'".format(volume_name))

        @api.doc(body=optional_from_snapshot,
                 description=("Create a new volume with the given details. "
                              " If `from_snapshot` is a snapshot and `volume_name`"
                              " already refers to an existing volume, roll back "
                              "that volume to that snapshot. If `from_snapshot` "
                              "is a snapshot, `from_volume` is an existing volume "
                              "and `volume_name` doesn't already exist, create a "
                              "clone of `from_volume` named `volume_name`, in the "
                              "state at `from_snapshot`."))
        @api.expect(optional_from_snapshot, validate=True)
        def put(self, volume_name):
            data = marshal(apis.api.payload, optional_from_snapshot)

            if data['from_volume'] and data['from_snapshot']:
                backend().clone_volume(volume_name, data['from_volume'], data['from_snapshot'])

            elif data['from_snapshot']:
                backend().rollback_volume(volume_name, data['from_snapshot'])
            else:
                backend().create_volume(volume_name, **dict_without(dict(data),
                                                                  'from_snapshot',
                                                                  'from_volume',
                                                                  'name'))

        @api.doc(description=("Restrict the volume named *volume_name*"
                              " but do not actually delete it"),
                 security='sso')
        @api.response(204, description="Successfully restricted",
                      model=None)
        @api.response(403, description="Unauthorised",
                      model=None)
        def delete(self, volume_name):
            backend().restrict_volume(volume_name)

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
            return backend().get_snapshots(volume_name)


    @api.route('/volumes/<path:volume_name>/snapshots/<string:snapshot_name>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    class Snapshots(Resource):

        @api.doc(description="Get the current information for a given snapshot")
        @api.marshal_with(snapshot_model)
        def get(volume_name, snapshot_name):
            return backend().get_snapshot(volume_name, snapshot_name)

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
