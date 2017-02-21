#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import apis
from apis.common.auth import in_group
from apis.common import ADMIN_GROUP
from utils import dict_without, filter_none

import logging
import traceback
from contextlib import contextmanager
from functools import partial

from flask_restplus import Namespace, Resource, fields, marshal
from flask import current_app

api = Namespace('/',
                description='Storage operations')

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


VOLUME_NAME_DESCRIPTION = ("The name of the volume. "
                           "Must not contain leading /")

SUBSYSTEM_MAPPING = {'netapp': 'NetappStorage',
                     'ceph': 'DummyStorage',
                     'dummy': 'DummyStorage'}

SUBSYSTEM_DESCRIPTION = ("The subsystem to run the command on."
                         " Must be one of: {}"
                         .format(", ".join(SUBSYSTEM_MAPPING.keys())))


@contextmanager
def exception_is_errorcode(api, exception, error_code, message=None):
    """
    Context to make sure all Exceptions of a given type calls an
    api.abort with a suitable error and corresponding message.

    If no message is passed, use str() on the exception.
    """
    try:
        yield
    except exception as e:
        message = str(e) if message is None else message
        api.abort(error_code, message)


keyerror_is_404 = partial(exception_is_errorcode, api=api,
                          exception=KeyError, error_code=404)
keyerror_is_400 = partial(exception_is_errorcode, api=api,
                          exception=KeyError, error_code=400)
valueerror_is_400 = partial(exception_is_errorcode, api=api,
                            exception=ValueError, error_code=400)


def backend(backend_name):
    """
    Return the actual backend object as given by backend_name. Has
    to be a function due to the app context not being available
    until later.
    """
    with exception_is_errorcode(api, KeyError, 404,
                                message=("No such subsystem. "
                                         "Allowed values are: {}")
                                .format(", ".join(SUBSYSTEM_MAPPING.keys()))):
        canonical_name = SUBSYSTEM_MAPPING[backend_name]
    try:
        return current_app.extensions[canonical_name]
    except KeyError:
        log.error("Backend {} not installed, using dummy back-end"
                  .format(canonical_name))
        return current_app.extensions['DummyStorage']


policy_rule_list_field = fields.List(fields.String(
    example="10.10.10.1/24",
    min_length=1))

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
    'uuid': fields.String(min_length=1),
    'active_policy_name': fields.String(min_length=1),
    'aggregate_name': fields.String(min_length=1),
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
    'rules': policy_rule_list_field
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

policy_rule_write_model = api.model('PolicyRule',
                                    {'rules': policy_rule_list_field})


@api.errorhandler
def default_error_handler(error):    # pragma: no cover
    log.warning(traceback.format_exc())
    return {'message': str(error)}, getattr(error, 'code', 500)


@api.route('/<string:subsystem>/volumes/')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
class AllVolumes(Resource):
    @api.doc(description="Get a list of all volumes",
             id='get_volumes')
    @api.marshal_with(volume, as_list=True)
    def get(self, subsystem):
        return backend(subsystem).volumes


@api.route('/<string:subsystem>/volumes/<path:volume_name>')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class Volume(Resource):

    @api.marshal_with(volume, description="The volume named volume_name")
    @api.doc(description="Get a specific volume by name")
    @api.response(404, description="No such volume exists")
    def get(self, subsystem, volume_name):
        assert "/snapshots" not in volume_name
        log.info("GET for {}".format(volume_name))
        with keyerror_is_404():
            return backend(subsystem).get_volume(volume_name)

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
    @in_group(api, ADMIN_GROUP)
    def post(self, subsystem, volume_name):
        assert "/snapshots" not in volume_name
        data = marshal(apis.api.payload, optional_from_snapshot)

        if data['from_volume'] and data['from_snapshot']:
            with keyerror_is_404(), valueerror_is_400():
                backend(subsystem).clone_volume(volume_name, data['from_volume'],
                                                data['from_snapshot'])
            return '', 201

        elif data['from_snapshot']:

            with keyerror_is_404():
                backend(subsystem).rollback_volume(
                    volume_name,
                    restore_snapshot_name=data['from_snapshot'])
        else:
            with valueerror_is_400(), keyerror_is_400():
                backend(subsystem).create_volume(volume_name,
                                                 **dict_without(dict(data),
                                                                'from_snapshot',
                                                                'from_volume',
                                                                'name'))

    @api.doc(description=("Restrict the volume named *volume_name*"
                          " but do not actually delete it"))
    @api.response(204, description="Successfully restricted",
                  model=None)
    @in_group(api, ADMIN_GROUP)
    def delete(self, subsystem, volume_name):
        assert "/snapshots" not in volume_name
        with keyerror_is_404():
            backend(subsystem).restrict_volume(volume_name)
        return '', 204

    @api.doc(description="Partially update volume_name")
    @api.expect(volume_writable_model, validate=True)
    @in_group(api, ADMIN_GROUP)
    def patch(self, subsystem, volume_name):
        assert "/snapshots" not in volume_name
        data = filter_none(marshal(apis.api.payload, volume_writable_model))
        log.info("PATCH with payload {}".format(str(data)))
        if data:
            with keyerror_is_404():
                backend(subsystem).patch_volume(volume_name, **data)
        else:
            raise api.abort(400, "No PATCH data provided!")


@api.route('/<string:subsystem>/volumes/<path:volume_name>/snapshots')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class AllSnapshots(Resource):
    @api.marshal_with(snapshot_model, description="All snapshots for the volume",
                      as_list=True)
    def get(self, subsystem, volume_name):
        assert "/snapshots" not in volume_name
        return backend(subsystem).get_snapshots(volume_name)


@api.route('/<string:subsystem>/volumes/<path:volume_name>/snapshots/<string:snapshot_name>')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('snapshot_name', 'The snapshot name')
class Snapshots(Resource):

    @api.doc(description="Get the current information for a given snapshot")
    @api.marshal_with(snapshot_model)
    def get(self, subsystem, volume_name, snapshot_name):
        with keyerror_is_404():
            return backend(subsystem).get_snapshot(volume_name, snapshot_name)

    @api.response(409, description=("Too many snapshots, cannot create another. "
                                    "Try `purge_old_if_needed=true`."))
    @api.response(201, description="Successfully created a snapshot")
    @api.expect(snapshot_put_model)
    @api.doc(description=("Create a new snapshot of *volume_name*"
                          " under *snapshot_name*"))
    def post(self, subsystem, volume_name, snapshot_name):
        log.info("Creating snapshot {} for volume {}"
                 .format(snapshot_name, volume_name))
        with keyerror_is_404(), valueerror_is_400():
            backend(subsystem).create_snapshot(volume_name, snapshot_name)
        return '', 201

    @api.doc(description=("Delete the snapshot"))
    @api.response(204, description="Successfully deleted",
                  model=None)
    @api.response(404, description="No such snapshot",
                  model=None)
    @in_group(api, ADMIN_GROUP)
    def delete(self, subsystem, volume_name, snapshot_name):
        with keyerror_is_404():
            backend(subsystem).delete_snapshot(volume_name, snapshot_name)
        return '', 204


@api.route('/<string:subsystem>/volumes/<path:volume_name>/locks')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.doc(description="Get the host locking the volume, if any")
class AllLocks(Resource):
    @api.marshal_with(lock_model, as_list=True,
                      description=("An empty list (if no locks were"
                                   " held) or a single dict describing the"
                                   " host holding the lock"))
    def get(self, subsystem, volume_name):
        with keyerror_is_404():
            mby_lock = backend(subsystem).locks(volume_name)
            return [] if mby_lock is None else [{"host": mby_lock}]


@api.route('/<string:subsystem>/volumes/<path:volume_name>/locks/<string:host>')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('host', "the host holding the lock in question")
class Locks(Resource):
    @api.doc(description="Lock the volume with host holding the lock")
    @api.response(201, "A new lock was added")
    @in_group(api, ADMIN_GROUP)
    def put(self, subsystem, volume_name, host):
        with valueerror_is_400(), keyerror_is_404():
            backend(subsystem).create_lock(volume_name, host)
        return '', 201

    @api.doc(description="Force the lock for the host")
    @api.response(204, description="Lock successfully forced")
    @in_group(api, ADMIN_GROUP)
    def delete(self, subsystem, volume_name, host):
        with keyerror_is_404():
            backend(subsystem).remove_lock(volume_name, host)
        return '', 204


@api.route('/<string:subsystem>/volumes/<path:volume_name>/export')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
class AllExports(Resource):
    @api.marshal_with(export_policy_model,
                      description="The current ACL for the given volume",
                      as_list=True)
    @api.doc(description="Get the full ACL for the volume")
    @in_group(api, ADMIN_GROUP)
    def get(self, subsystem, volume_name):
        with keyerror_is_404():
            return [{'policy_name': policy,
                     'rules': rules} for policy, rules in
                    backend(subsystem).policies(volume_name)]


@api.route('/<string:subsystem>/volumes/<path:volume_name>/export/<string:policy>')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('policy', "The policy to operate on")
class Export(Resource):

    @api.marshal_with(export_policy_model,
                      description="Get the rules of a specific policy")
    @api.doc(description="Display the rules of a given policy")
    @in_group(api, ADMIN_GROUP)
    def get(self, subsystem, volume_name, policy):
        with keyerror_is_404():
            rules = backend(subsystem).get_policy(volume_name, policy)
            return {'policy_name': policy,
                    'rules': rules}

    @api.doc(description="Grant hosts matching a given pattern access to the given volume")
    @api.response(201, description="The provided access rules were added")
    @api.response(404, description="There is no such volume")
    @api.response(400, description="A policy with that name already exists")
    @api.expect(policy_rule_write_model, validate=True)
    @in_group(api, ADMIN_GROUP)
    def post(self, subsystem, volume_name, policy):
        rules = marshal(apis.api.payload, policy_rule_write_model)['rules']
        with keyerror_is_404(), valueerror_is_400():
            backend(subsystem).create_policy(volume_name, policy, rules)
        return '', 201

    @api.doc(description=("Delete the entire policy"))
    @api.response(204, description="Successfully deleted the policy")
    @api.response(404, description="No such policy exists")
    @in_group(api, ADMIN_GROUP)
    def delete(self, subsystem, volume_name, policy):
        with keyerror_is_404():
            backend(subsystem).remove_policy(volume_name, policy)
        return '', 204


@api.route('/<string:subsystem>/volumes/<path:volume_name>/export/<string:policy>/<path:rule>')
@api.param('subsystem', SUBSYSTEM_DESCRIPTION)
@api.param('volume_name', VOLUME_NAME_DESCRIPTION)
@api.param('policy', "The policy to operate on")
@api.param('rule', "The policy rule to operate on")
class ExportRule(Resource):

    @api.doc(description="Grant hosts matching a given pattern access to the given volume")
    @api.response(201, description="The provided access rule was added")
    @in_group(api, ADMIN_GROUP)
    def put(self, subsystem, volume_name, policy, rule):
        backend(subsystem).ensure_policy_rule_present(volume_name, policy, rule)
        return '', 201

    @api.doc(description=("Delete rule from policy"))
    @api.response(204, description="Successfully deleted the rule")
    @api.response(404, description="No such policy, rule or volume exists")
    @in_group(api, ADMIN_GROUP)
    def delete(self, subsystem, volume_name, policy, rule):
        backend(subsystem).ensure_policy_rule_absent(volume_name, policy, rule)
        return '', 204
