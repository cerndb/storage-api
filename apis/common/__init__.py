#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import apis
from .auth import in_group
from utils import dict_without, filter_none

import logging
import traceback

from flask_restplus import Resource, fields, marshal
from flask import current_app

VOLUME_NAME_DESCRIPTION = ("The name of the volume. "
                           "Must not contain leading /")
ADMIN_GROUP = 'admin-group'

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def init_namespace(api, backend_name):
    def backend():
        """
        Return the actual backend object as given by backend_name. Has
        to be a function due to the app context not being available
        until later.
        """
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

    export_policy_model = api.model('Export Policy', {
        'policy_name': fields.String(min_length=1,
                                     example="allow_cluster_x"),
        'rules': fields.List(fields.String(example=["10.10.10.1/24",
                                                    "123.11.12.1"],
                                           min_length=1))
        })

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

    @api.errorhandler
    def default_error_handler(error):    # pragma: no cover
        log.warning(traceback.format_exc())
        return {'message': str(error)}, getattr(error, 'code', 500)

    @api.errorhandler(KeyError)
    def key_error_handler(error):
        """
        Key Errors represent something being abscent in the back-end.
        """
        log.warning(traceback.format_exc())
        return {'message': str(error)}, 404

    @api.errorhandler(ValueError)
    def value_error_handler(error):
        """
        ValueErrors represent invalid input.
        """
        log.warning(traceback.format_exc())
        return {'message': str(error)}, 400

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
            assert "/snapshots" not in volume_name
            log.info("GET for {}".format(volume_name))
            return backend().get_volume(volume_name)

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
        @in_group(ADMIN_GROUP)
        def put(self, volume_name):
            assert "/snapshots" not in volume_name
            data = marshal(apis.api.payload, optional_from_snapshot)

            if data['from_volume'] and data['from_snapshot']:
                backend().clone_volume(volume_name, data['from_volume'], data['from_snapshot'])
                return '', 201

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
        @in_group(ADMIN_GROUP)
        def delete(self, volume_name):
            assert "/snapshots" not in volume_name
            backend().restrict_volume(volume_name)
            return '', 204

        @api.doc(description="Partially update volume_name",
                 security='sso')
        @api.response(403, description="Unauthorised",
                      model=None)
        @api.expect(volume_writable_model, validate=True)
        @in_group(ADMIN_GROUP)
        def patch(self, volume_name):
            assert "/snapshots" not in volume_name
            data = filter_none(marshal(apis.api.payload, volume_writable_model))
            log.info("PATCH with payload {}".format(str(data)))
            if data:
                backend().patch_volume(volume_name, data)
            else:
                raise ValueError("No PATCH data provided!")

    @api.route('/volumes/<path:volume_name>/snapshots')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    class AllSnapshots(Resource):
        @api.marshal_with(snapshot_model, description="All snapshots for the volume",
                          as_list=True)
        def get(self, volume_name):
            assert "/snapshots" not in volume_name
            return backend().get_snapshots(volume_name)

    @api.route('/volumes/<path:volume_name>/snapshots/<string:snapshot_name>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    class Snapshots(Resource):

        @api.doc(description="Get the current information for a given snapshot")
        @api.marshal_with(snapshot_model)
        def get(self, volume_name, snapshot_name):
            return backend().get_snapshot(volume_name, snapshot_name)

        @api.response(409, description=("Too many snapshots, cannot create another. "
                                        "Try `purge_old_if_needed=true`."))
        @api.response(403, description="Insufficient rights/not logged in")
        @api.response(201, description="Successfully created a snapshot")
        @api.expect(snapshot_put_model)
        @api.doc(description=("Create a new snapshot of *volume_name*"
                              " under *snapshot_name*"))
        def put(self, volume_name, snapshot_name):
            log.info("Creating snapshot {} for volume {}"
                     .format(snapshot_name, volume_name))
            backend().create_snapshot(volume_name, snapshot_name)
            return '', 201

        @api.doc(description=("Delete the snapshot"),
                 security='sso')
        @api.response(204, description="Successfully deleted",
                      model=None)
        @api.response(403, description="Unauthorised",
                      model=None)
        @api.response(404, description="No such snapshot",
                      model=None)
        @in_group(ADMIN_GROUP)
        def delete(self, volume_name, snapshot_name):
            backend().delete_snapshot(volume_name, snapshot_name)
            return '', 204

    @api.route('/volumes/<path:volume_name>/locks')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    @api.doc(description="Get the host locking the volume, if any")
    class AllLocks(Resource):
        @api.marshal_with(lock_model, as_list=True,
                          description=("An empty list (if no locks were"
                                       " held) or a single dict describing the"
                                       " host holding the lock"))
        def get(self, volume_name):
            return backend().locks(volume_name)

    @api.route('/volumes/<path:volume_name>/locks/<string:host>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    @api.param('host', "the host holding the lock in question")
    class Locks(Resource):
        @api.doc(description="Lock the volume with host holding the lock",
                 security='sso')
        @api.response(201, "A new lock was added")
        @in_group(ADMIN_GROUP)
        def put(self, volume_name, host):
            backend().add_lock(volume_name, host)
            return '', 201

        @api.doc(description="Force the lock for the host",
                 security="sso")
        @api.response(403, description="Unauthorized")
        @api.response(204, description="Lock successfully forced")
        @in_group(ADMIN_GROUP)
        def delete(self, volume_name, host):
            backend().remove_lock(volume_name, host)
            return '', 204

    @api.route('/volumes/<path:volume_name>/export')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    class AllExports(Resource):
        @api.marshal_with(export_policy_model,
                          description="The current ACL for the given volume",
                          as_list=True)
        @api.doc(description="Get the full ACL for the volume")
        @in_group(ADMIN_GROUP)
        def get(self, volume_name):
            return backend().policies(volume_name)

    @api.route('/volumes/<path:volume_name>/export/<string:policy>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    @api.param('policy', "The policy to operate on")
    class Export(Resource):

        @api.marshal_with(export_policy_model,
                          description="Get the rules of a specific policy")
        @api.doc(description="Display the rules of a given policy")
        @in_group(ADMIN_GROUP)
        def get(self):
            return backend().get_policy(volume_name, policy)

        @api.doc(description="Grant hosts matching a given pattern access to the given volume")
        @api.response(201, description="The provided access rules were added")
        @in_group(ADMIN_GROUP)
        def put(self, volume_name, policy):
            # DATA = list of strings, potentially empty (no access)
            rules = []
            backend().add_policy(volume_name, policy, rules)
            return '', 201

        @api.doc(description=("Delete the entire policy"))
        @api.response(204, description="Successfully deleted the policy")
        @api.response(404, description="No such policy exists")
        @in_group(ADMIN_GROUP)
        def delete(self, volume_name, policy):
            backend().remove_policy(volume_name, policy)
            return '', 204

    @api.route('/volumes/<path:volume_name>/export/<string:policy>/<path:rule>')
    @api.param('volume_name', VOLUME_NAME_DESCRIPTION)
    @api.param('policy', "The policy to operate on")
    class Export(Resource):

        @api.doc(description="Grant hosts matching a given pattern access to the given volume")
        @api.response(201, description="The provided access rule was added")
        @in_group(ADMIN_GROUP)
        def put(self, volume_name, rule):
            backend().policy_rule_present(volume_name, policy, rule)
            return '', 201

        @api.doc(description=("Delete rule from policy"))
        @api.response(204, description="Successfully deleted the rule")
        @api.response(404, description="No such policy, rule or volume exists")
        @in_group(ADMIN_GROUP)
        def delete(self, volume_name, policy, rule):
            backend().policy_rule_absent(volume_name, policy, rule)
            return '', 204
