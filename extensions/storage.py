# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

"""
This is a generalised back-end for storage systems.

In general, methods are expected to raise KeyErrors on 404-type errors
(e.g. something not found), and ValueErrors on invalid input. In both
cases, reasonable descriptions of what went wrong should be included,
and -- if possible -- suggestions on how to fix the situation.
"""


from abc import ABCMeta, abstractmethod
import logging
from contextlib import contextmanager
import functools
from typing import Dict, Any
import re

from ordered_set import OrderedSet
import cerberus
import flask
import netapp.api

log = logging.getLogger(__name__)
SCHEMAS = [('volume', {
    'name': {'type': 'string', 'minlength': 1,
             'required': True},

    'uuid': {'type': 'string', 'minlength': 1,
             'required': False},
    'active_policy_name': {'type': 'string', 'minlength': 1,
                           'required': False},
    'junction_path': {'type': 'string', 'minlength': 1,
                      'required': False},
    'aggregate_name': {'type': 'string', 'minlength': 1,
                       'required': False},
    'state': {'type': 'string', 'minlength': 1,
              'required': False},
    'size_used': {'type': 'integer', 'min': 0,
                  'required': True},
    'size_total': {'type': 'integer', 'min': 0,
                   'required': True},
    'filer_address': {'type': 'string', 'minlength': 1,
                      'required': True},
    'creation_time': {'type': 'datetime',
                      'required': False},
    'compression_enabled': {'type': 'boolean',
                            'required': False},
    'inline_compression': {'type': 'boolean',
                           'required': False},
    'percentage_snapshot_reserve': {'type': 'integer',
                                    'required': False},
    'percentage_snapshot_reserve_used': {'type': 'integer',
                                         'required': False},
    'caching_policy': {'type': 'string',
                       'required': False,
                       'nullable': True},
})]

cerberus.schema_registry.extend(SCHEMAS)


class ValidationError(Exception):
    """
    An Exception raised when a return value fails to pass its schema
    validation.
    """
    pass


def vol_404(volume_name: str) -> str:
    return "No such volume: {}".format(volume_name)


def validate_value(v: cerberus.Validator, value: Dict[str, Any]):
    validation_result = v.validate(value, normalize=True)
    if not validation_result:
        raise ValidationError(v.errors)  # pragma: no cover
    else:
        return v.normalized(value)


def normalised_with(schema_name: str,
                    allow_unknown: bool=False,
                    as_list: bool=False):
    """
    A decorator to normalise and validate the return values of a
    function according to a schema.

    If as_list is True, validate and normalise each entry in the
    returned list.

    Raises a ValidationError if the schema was not correctly validated.
    """

    def validator_decorator(func):
        @functools.wraps(func)
        def inner_wrapper(*args, **kwargs):
            schema = cerberus.schema_registry.get(name=schema_name)
            v = cerberus.Validator(schema, allow_unknown=allow_unknown)
            return_value = func(*args, **kwargs)

            if as_list:
                if isinstance(return_value, str):
                    raise ValidationError("Expected a list!")  # pragma: no cover
                try:
                    return [validate_value(v, x) for x in return_value]
                except TypeError:  # pragma: no cover
                    raise ValidationError("Expected a list!")
            else:
                return validate_value(v, return_value)

        return inner_wrapper
    return validator_decorator


def patch_and_diff(previous, new):
    """
    Replace all keys in previous with their values in new, returning a
    list of keys for which the values changed and the updated previous.
    """
    changed_keys = []
    for k, v in new.items():
        if k in previous:
            if previous[k] != v:
                previous[k] = v
                changed_keys.append(k)
        else:
            previous[k] = v
            changed_keys.append(k)
    return changed_keys, previous


@contextmanager
def annotate_exception(exception, annotation):
    """
    Context manager to annotate a particular type of exception with a
    descriptive text.

    Example:
    ```
    with annotate_exception(KeyError, "no such item!"):
      a = foo['key']
    ```
    """
    try:
        yield
    except exception:
        raise exception(annotation)


class StorageBackend(metaclass=ABCMeta):

    def __repr__(self):
        return "{}({})".format(type(self).__name__, str(self.__dict__))

    @property
    @abstractmethod
    def volumes(self):
        """
        Return all active and usable volumes of the storage backend as
        a list of dictionaries (see get_volume() for their format).

        Read-only property.
        """
        return NotImplemented

    @abstractmethod
    def get_volume(self, volume_name):
        """
        Return (the data for) a specific volume as a dictionary with (at
        least) the following elements:

        - name
        - size_used
        - size_total
        - filer_address

        Back-ends are allowed to add implementation-specific
        elements.

        Raises:
            KeyError: if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def restrict_volume(self, volume_name):
        """
        Restrict or delete a volume. This will cause it to not appear in
        volumes or get_volume(), as if the volume never existed.

        What action is actually performed is platform-dependent, but
        should be semantically as close to a delete operation as
        possible.

        Notably, there is no guarantee that it is possible to create a
        new volume with the same name as a recently deleted volume.
        """
        return NotImplemented

    @abstractmethod
    def patch_volume(self, volume_name, **data):
        """
        Update a volume with data from **data.

        Raises:
            ValueError: on poorly formatted data, or invalid data
                entries/attempts to write to read-only fields
            KeyError: if no volume named volume_name exists.
        """
        return NotImplemented

    @abstractmethod
    def create_volume(self, volume_name, **fields):
        """
        Create a new volume with a given name and the provided data
        fields.

        `fields` can be at least:

        - size_total

        Raises:
            ValueError: if the data is malformed
            KeyError: if the volume already exists

        Returns:
            The created volume.

        Back-ends are allowed to add implementation-specific elements.
        """
        return NotImplemented

    @abstractmethod
    def locks(self, volume_name):
        """
        Return the string naming the host currently holding a lock on
        the volume named volume_name, or None if there were no locks.

        Raises:
            KeyError: if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def create_lock(self, volume_name, host_owner):
        """
        Install a lock held by the host host_owner on the given volume.

        Raises:
            ValueError: if a lock is already held on that volume by
                another host
            KeyError: if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def remove_lock(self, volume_name, host_owner):
        """
        Remove/break/force the lock on a volume, if held by
        host_owner. Does nothing if no locks were held on volume_name,
        or if the lock wasn't held by host_owner.

        Raises:
            KeyError: if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def policies(self):
        """
        Return a list of export policies for the given back-end, as a list
        of name/value tuples.

        Example::

            ["my_policy", ["127.0.0.1", "10.10.10.1/24"]]

        Notably, no policies would yield []. The interpretation
        of these values are up to the implementation, but it can be
        assumed that no policies is not the same thing as a policy with
        no rules.

        Raises:
            KeyError: if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def get_policy(self, policy_name):
        """
        Return a (potentially empty) list of export policies in the form
        of strings representing IP numbers, with possible masks
        associated with the given policy.

        Raises:
            KeyError: if volume_name does not exist or does not have a policy named policy_name
        """
        return NotImplemented

    @abstractmethod
    def set_policy(self, volume_name, policy_name):
        """
        Set a policy

        Raises:
          KeyError: if volume_name does not exist
          ValueError: if policy_name does not exist
        """

        return NotImplemented

    @abstractmethod
    def create_policy(self, policy_name, rules):
        """
        Add a new policy with a set of rules to a given volume

        Raises:
            ValueError: if there is already a policy with that name
        """
        return NotImplemented

    @abstractmethod
    def remove_policy(self, policy_name):
        """
        Remove a policy. After removal, it must be possible to create a
        new policy with the same name.

        Raises:
            KeyError: if no such volume or policy exists
        """

        return NotImplemented

    @abstractmethod
    def clone_volume(self, clone_volume_name,
                     from_volume_name, from_snapshot_name):
        """
        Create a clone of a volume from a provided snapshot.

        Raises:
            KeyError: if no such volume or snapshot exists
            ValueError: if clone_volume_name already exists
        """
        return NotImplemented

    @abstractmethod
    def create_snapshot(self, volume_name, snapshot_name):
        """
        Make a snapshot from the current state of a volume.

        Raises:
            KeyError: if no volume named volume_name exists
            ValueError: if there is already a snapshot named snapshot_name,
                or if the name is invalid.
        """
        return NotImplemented

    @abstractmethod
    def get_snapshot(self, volume_name, snapshot_name):
        """
        Get the data associated with the snapshot.

        Back-ends are allowed to add additional keys.

        Raises:
            KeyError: if no such volume or snapshot exists
        """

        return NotImplemented

    @abstractmethod
    def delete_snapshot(self, volume_name, snapshot_name):
        """
        Delete, or the closest possible equivalent, a given snapshot.

        Raises:
            KeyError: if no such volume or snapshot exists
        """
        return NotImplemented

    @abstractmethod
    def get_snapshots(self, volume_name):
        """
        Return a list of snapshots for volume_name.

        Raises:
            KeyError: if no such volume exists.
        """
        return NotImplemented

    @abstractmethod
    def rollback_volume(self, volume_name, restore_snapshot_name):
        """
        Roll back a volume to a snapshot.

        Raises:
            KeyError: if volume_name does not exist or does not have a
                snapshot named restore_snapshot_name.
        """
        return NotImplemented

    @abstractmethod
    def ensure_policy_rule_present(self, policy_name, rule):
        """
        Idempotently ensure that a given export policy (as represented
        by an IP with optional mask) is present in the rules of a given
        policy. If it is not present it will be added.

        Raises:
            KeyError: if no such policy exists.
        """

        return NotImplemented

    @abstractmethod
    def ensure_policy_rule_absent(self, policy_name, rule):
        """
        Idempotently ensure that a given export policy (as represented
        by an IP with optional mask) is absent in the rules of a given
        policy. Will delete it if present, otherwise give no warning.

        Raises:
            KeyError: if no such policy exists.
        """

        return NotImplemented

    def init_app(self, app: flask.Flask):
        """
        Initialise a Flask app context with the storage system.

        Args:
            app (flask.Flask): The application to install the storage
                system back-end in


        Example::

            app = Flask(__name__)
            netapp = NetAppStorage()
            netapp.init_app(app=app)
        """

        if not hasattr(app, 'extensions'):   # pragma: no coverage
            app.extensions = {}

        class_name = self.__class__.__name__
        app.extensions[class_name] = self


class DummyStorage(StorageBackend):
    """
    This is a dummy storage back-end meant for testing. It will persist
    data given to it in RAM and follow the standard API provided by the
    base class above, but that is about it.
    """

    def raise_if_volume_absent(self, volume_name: str):
        """
        Raise a `KeyError` with an appropriate message if a volume is
        absent.
        """
        if volume_name not in self.vols:
            raise KeyError(vol_404(volume_name))

    def raise_if_snapshot_absent(self, volume_name: str, snapshot_name: str):
        """
        Raise a `KeyError` with an appropriate message if a
        snapshot is absent.

        This implies first running `raise_if_volume absent(volume_name)`.
        """
        self.raise_if_volume_absent(volume_name)

        if snapshot_name not in self.snapshots_store[volume_name]:
            raise KeyError("No such snapshot exists for volume '{}': '{}'"
                           .format(volume_name, snapshot_name))

    def __init__(self):
        self.vols = {}  # type: Dict[str, Dict[str, Any]]
        self.locks_store = {}  # type: Dict[str, str]
        self.rules_store = {}  # type: Dict[str, str]
        self.snapshots_store = {}  # type: Dict[str, Dict[str, List[str]]]
        self.policies_store = {}  # type: Dict[str, List[str]]

    @property
    def volumes(self):
        return self._volumes()

    @normalised_with('volume', as_list=True)
    def _volumes(self):
        return list(self.vols.values())

    @normalised_with('volume', allow_unknown=True)
    def get_volume(self, volume_name):
        log.info("Trying to get volume {}".format(volume_name))
        with annotate_exception(KeyError, vol_404(volume_name)):
            return self.vols[volume_name]

    def restrict_volume(self, volume_name):
        log.info("Restricting volume {}".format(volume_name))
        with annotate_exception(KeyError, vol_404(volume_name)):
            self.vols.pop(volume_name)
        self.locks_store.pop(volume_name, None)
        self.rules_store.pop(volume_name, None)
        self.snapshots_store.pop(volume_name, None)

    def patch_volume(self, volume_name, **data):
        log.info("Updating volume {} with data {}"
                 .format(volume_name, data))
        for key in data:
            with annotate_exception(KeyError, vol_404(volume_name)):
                self.vols[volume_name][key] = data[key]

    def create_volume(self, volume_name, **kwargs):
        log.info("Adding new volume '{}': {}"
                 .format(volume_name, str(kwargs)))

        if volume_name in self.vols:
            raise KeyError("Volume {} already exists!".format(volume_name))

        size_total = kwargs.get('size_total', None)
        filer_address = kwargs.get('filer_address', None)

        data = {'name': str(volume_name),
                'size_used': 0,
                'size_total': 0 if size_total is None else size_total,
                'filer_address':
                "dummy-filer" if filer_address is None else filer_address}

        self.vols[volume_name] = data
        self.locks_store.pop(volume_name, None)
        self.snapshots_store[volume_name] = {}
        return self.vols[volume_name]

    def locks(self, volume_name):
        self.raise_if_volume_absent(volume_name)

        if volume_name not in self.locks_store:
            return None
        else:
            return self.locks_store[volume_name]

    def create_lock(self, volume_name, host_owner):
        self.raise_if_volume_absent(volume_name)

        log.info("Host_Owner {} is locking {}".format(host_owner, volume_name))
        if volume_name in self.locks_store and self.locks_store[volume_name] != host_owner:
            raise ValueError("{} is already locked by {}!"
                             .format(volume_name,
                                     self.locks_store[volume_name]))

        self.locks_store[volume_name] = host_owner

    def remove_lock(self, volume_name, host_owner):
        self.raise_if_volume_absent(volume_name)

        with annotate_exception(KeyError, vol_404(volume_name)):
            if host_owner == self.locks_store[volume_name]:
                self.locks_store.pop(volume_name)

    @property
    def policies(self):
        return [{'name': name, 'rules': rules}
                for name, rules in self.rules_store.items()]

    def get_policy(self, policy_name):
        return self.rules_store[policy_name]

    def set_policy(self, volume_name, policy_name):
        self.raise_if_volume_absent(volume_name)
        if policy_name not in self.rules_store:
            raise ValueError("No such policy: {}".format(policy_name))

        self.vols[volume_name]['active_policy_name'] = policy_name

    def create_policy(self, policy_name, rules):
        log.info("Adding policy {} with rules {}"
                 .format(policy_name, rules))
        self.rules_store[policy_name] = list(OrderedSet(rules))

    def remove_policy(self, policy_name):
        log.info("Removing policy {}"
                 .format(policy_name))
        self.rules_store.pop(policy_name)

    def clone_volume(self, clone_volume_name,
                     from_volume_name, from_snapshot_name):
        log.info("Cloning volume {target} from {source}:{snapshot}"
                 .format(target=clone_volume_name, source=from_volume_name,
                         snapshot=from_snapshot_name))
        self.raise_if_snapshot_absent(from_volume_name, from_snapshot_name)

        if clone_volume_name in self.vols:
            raise ValueError("Name already in use!")

        with annotate_exception(KeyError, vol_404(from_volume_name)):
            self.vols[clone_volume_name] = self.vols[from_volume_name]

    def create_snapshot(self, volume_name, snapshot_name):
        log.info("Creating snapshot {}:{}".format(volume_name, snapshot_name))
        with annotate_exception(KeyError, vol_404(volume_name)):
            self.snapshots_store[volume_name][snapshot_name] = {
                'name': snapshot_name}

    def get_snapshot(self, volume_name, snapshot_name):
        log.info("Fetching snapshot {}:{}".format(volume_name, snapshot_name))
        self.raise_if_snapshot_absent(volume_name, snapshot_name)
        return self.snapshots_store[volume_name][snapshot_name]

    def delete_snapshot(self, volume_name, snapshot_name):
        log.info("Deleting {} on {}".format(snapshot_name, volume_name))
        self.raise_if_snapshot_absent(volume_name, snapshot_name)
        self.snapshots_store[volume_name].pop(snapshot_name)

    def get_snapshots(self, volume_name):
        log.info("Getting snapshots for {}".format(volume_name))
        self.raise_if_volume_absent(volume_name)
        return list(self.snapshots_store[volume_name].values())

    def rollback_volume(self, volume_name, restore_snapshot_name):
        log.info("Restoring '{}' to '{}'"
                 .format(volume_name, restore_snapshot_name))
        self.raise_if_snapshot_absent(volume_name, restore_snapshot_name)

    def ensure_policy_rule_present(self, policy_name, rule):
        if rule not in self.rules_store[policy_name]:
            self.rules_store[policy_name].append(rule)

    def ensure_policy_rule_absent(self, policy_name, rule):
        stored_rules = self.rules_store[policy_name]
        self.rules_store[policy_name] = list(filter(
            lambda x: x != rule, stored_rules))


class NetappStorage(StorageBackend):
    """
    A Back-end for a NetApp storage system.
    """

    def __init__(self, netapp_server):
        """
        netapp_server is assumed to be configured to a vserver.
        """

        self.server = netapp_server
        import requests
        requests.packages.urllib3.disable_warnings()

    def format_volume(self, v):
        return {'size_total': v.size_total_bytes,
                'size_used': v.size_used_bytes,
                'filer_address': v.node_name,
                'aggregate_name': v.containing_aggregate_name,
                **v.__dict__}

    def format_policy(self, p):
        return {'name': p.name,
                'rules': [r[1] for r in p.rules]}

    def name_from_path(self, junction_path):
        """
        'Resolve' a junction path to a proper volume name.

        Raises KeyError if there was no such volume.
        """
        vols = self.server.volumes.filter(junction_path=junction_path)
        try:
            volume = next(vols)
        except StopIteration:
            raise KeyError(junction_path)

        return volume.name

    def node_junction_path(self, volume_name):
        """
        Convert a "volume_name" parameter to a node name and junction
        path.

        Returns:
          a tuple of `(node, junction path)`. If the string does not
          adhere to the format, it is assumed to contain only the
          junction path and the returned node is None.
        """
        try:
            node, junction_path = volume_name.split(":")
            return node, junction_path
        except ValueError:
            log.info("{} does not follow naming"
                     " convention node:junction_path, assume name."
                     .format(volume_name))
            return None, volume_name

    def parse_volume_name(self, volume_name_or_node_path):
        """
        Parse a volume name on the format name, or node:junction_path,
        always returning a unique name.
        """
        node, junction_path = self.node_junction_path(volume_name_or_node_path)
        if node is None:
            # Name did not follow name:junction_path convention. Assume name.
            return junction_path
        else:
            return self.name_from_path(junction_path)

    @property
    def volumes(self):
        """
        Explicitly ignores volumes belonging to aggr0 and volumes that
        are restricted.
        """

        return [self.format_volume(v) for v in self.server.volumes
                if not re.match("^aggr0.*", v.containing_aggregate_name)
                and not v.state == 'restricted']

    @normalised_with('volume', allow_unknown=True)
    def get_volume(self, volume_name):
        node, junction_path = self.node_junction_path(volume_name)
        try:
            if node is not None:
                volume = next(self.server.volumes.filter(
                    junction_path=junction_path, node=node))
            else:
                # Just a name was provided, not a node:junction_path
                volume_name = junction_path
                volume = self.server.volumes.single(volume_name=volume_name)
        except (StopIteration, IndexError):
            with annotate_exception(KeyError, vol_404(volume_name)):
                raise KeyError
        return self.format_volume(volume)

    def get_policy(self, policy_name):
        if policy_name not in [p.name for p in self.server.export_policies]:
            raise KeyError("No such policy exists: '{}'".format(policy_name))
        rules = [r[1] for r in self.server.export_rules_of(policy_name)]
        return rules

    def set_policy(self, volume_name, policy_name):
        volume_name = self.parse_volume_name(volume_name)

        self.server.set_volume_export_policy(volume_name=volume_name,
                                             policy_name=policy_name)

    def get_snapshots(self, volume_name):
        volume_name = self.parse_volume_name(volume_name)
        return [{'name': s} for s in self.server.snapshots_of(volume_name)]

    @property
    def policies(self):
        return [self.format_policy(p) for p in self.server.export_policies]

    def locks(self, volume_name):
        volume_name = self.parse_volume_name(volume_name)
        ls = [l.client_address for l in self.server.locks_on(volume_name)]
        if not ls:
            return None
        else:
            return ls

    def clone_volume(self, clone_volume_name,
                     from_volume_name, from_snapshot_name):

        junction_path = self.get_volume(clone_volume_name)['junction_path']

        self.server.clone_volume(from_volume_name, clone_volume_name,
                                 junction_path, from_snapshot_name)

    def create_snapshot(self, volume_name, snapshot_name):
        _node, junction_path = self.node_junction_path(volume_name)
        volume_name = self.name_from_path(junction_path)

        self.server.create_snapshot(volume_name, snapshot_name)

    def get_snapshot(self, volume_name, snapshot_name):
        volume_name = self.parse_volume_name(volume_name)
        snapshots = self.get_snapshots(volume_name)
        for snapshot in snapshots:
            if snapshot['name'] == snapshot_name:
                return snapshot
        raise ValueError("No such snapshot {}".format(snapshot_name))

    def remove_policy(self, policy_name):
        try:
            self.server.delete_export_policy(policy_name)
        except netapp.api.APIError as e:
            if e.errno == 15661:
                raise KeyError("Policy doesn't exist: '{}'".format(policy_name))
            else:
                raise e

    def create_policy(self, policy_name, rules):
        self.server.create_export_policy(policy_name, rules=rules)

    def delete_snapshot(self, volume_name, snapshot_name):
        volume_name = self.parse_volume_name(volume_name)
        try:
            self.server.delete_snapshot(volume_name, snapshot_name)
        except netapp.api.APIError as e:
            if e.errno == 15661:
                raise KeyError("No such snapshot {}".format(snapshot_name))
            else:
                raise e

    def rollback_volume(self, volume_name, restore_snapshot_name):
        volume_name = self.parse_volume_name(volume_name)
        self.get_snapshot(volume_name, restore_snapshot_name)
        self.server.rollback_volume_from_snapshot(volume_name, restore_snapshot_name)

    def ensure_policy_rule_present(self, policy_name, rule):
        rules = [r for _i, r in self.server.export_rules_of(policy_name)]
        if rule not in rules:
            self.server.add_export_rule(policy_name, rule)

    def ensure_policy_rule_absent(self, policy_name, rule):
        for index, stored_rule in self.server.export_rules_of(policy_name):
            if rule == stored_rule:
                self.server.remove_export_rule(policy_name, index)
                break

    @normalised_with('volume', allow_unknown=True)
    def create_volume(self, volume_name, **fields):
        """
        Important note: the volume "name" for NetApp is either a name,
        or a node name and junction path separated by colon. Please note
        that the node name is ignored, as the user cannot set the node
        name on creation.

        If creating a volume from a junction path, an *actual* name must
        be provided as a data field ('name') (and vice versa -- if
        creating with a name, junction path must be provided).
        """
        # Fixme: optionally include autosize_enabled etc

        node, junction_path = self.node_junction_path(volume_name)

        if node:
            log.warning("Ignoring provided node name '{}' for volume creation"
                        .format(node))

        if node is None:
            # Only name was given, get junction path from fields
            volume_name = junction_path
            junction_path = fields.get('junction_path', None)
        else:
            volume_name = fields.get('name', None)

        if not volume_name:
            raise ValueError("Must provide a volume name for NetApp back-ends!")
        if not junction_path:
            raise ValueError("Must provide a junction path for NetApp back-ends!")
        if not fields.get('size_total', None):
            raise ValueError("Must provide size_total for NetApp!")

        aggregate_name = None
        snapshot_reserve = fields.get('percentage_snapshot_reserve', None)
        compression = fields.get('compression_enabled', None)
        inline_compression = fields.get('inline_compression', None)
        export_policy_name = fields.get('active_policy_name', None)

        # None-patch the keys with default values.
        # This is needed, because the front-end gives us None if no
        # value was provided by the user.
        if snapshot_reserve is None:
            snapshot_reserve = 0
        if compression is None:
            compression = True
        if inline_compression is None:
            inline_compression = True

        if fields.get('aggregate_name', None):
            aggregate_name = fields['aggregate_name']
            log.debug("Using provided aggregate {}".format(aggregate_name))
        else:
            log.info("Aggregate not provided,"
                     " using the one with the most free space...")
            # sorted sorts ascending by default.
            with self.server.with_vserver(None):
                # Switch to cluster-mode for this operation
                aggregates = sorted(self.server.aggregates,
                                    key=lambda a: a.bytes_available,
                                    reverse=True)

            not_aggr0 = functools.partial(re.compile("(?!^aggr0.*)").match)

            for aggregate in aggregates:
                if not_aggr0(aggregate.name):
                    aggregate_name = aggregate.name
                    log.info("Picked aggregate {} for {}"
                             .format(aggregate_name,
                                     volume_name))
                    break
                else:
                    log.info("Skipping aggregate {} because it is aggr0"
                             .format(aggregate.name))

        assert aggregate_name, "Could not find a suitable aggregate!"

        try:
            self.server.create_volume(
                name=volume_name,
                size_bytes=fields['size_total'],
                junction_path=junction_path,
                percentage_snapshot_reserve=snapshot_reserve,
                compression=compression,
                inline_compression=inline_compression,
                export_policy_name=export_policy_name,
                aggregate_name=aggregate_name)
            return self.format_volume(
                self.server.volumes.single(volume_name=volume_name))
        except netapp.api.APIError as e:
            if e.errno == 17:
                raise KeyError("Volume {} already exists!".format(volume_name))
            else:
                raise e

    def create_lock(self, volume_name, host_owner):
        # There doesn't seem to be any way of implementing this. :(
        return NotImplemented

    def remove_lock(self, volume_name, host_owner):
        volume_name = self.parse_volume_name(volume_name)
        self.server.break_lock(volume_name, host_owner)

    def patch_volume(self, volume_name, **data):
        previous = self.get_volume(volume_name)

        changed_keys, updated_volume = patch_and_diff(previous, data)

        # Autosize:
        autosize_key = re.compile('autosize').match

        if any(autosize_key(k) for k in changed_keys):
            log.info("Updating autosize...")
            self.server.set_volume_autosize(
                previous['name'],
                max_size_bytes=updated_volume['max_autosize'],
                increment_bytes=updated_volume['autosize_increment'],
                autosize_enabled=updated_volume['autosize_enabled'])

        # Snapshot reserve space
        if 'percentage_snapshot_reserve' in changed_keys:
            log.info("Updating snapshot reserve space...")
            self.server.set_volume_snapshot_reserve(
                previous['name'],
                reserve_percent=updated_volume['percentage_snapshot_reserve'])

        # Compression
        if any(re.match('compression', k) for k in changed_keys):
            log.info("Updating compression...")
            self.server.set_compression(
                volume_name=previous['name'],
                enabled=updated_volume['compression_enabled'],
                inline=updated_volume['inline_compression'])

        # Active export policy
        if 'active_policy_name' in changed_keys:
            log.info("Updating policy name...")
            self.server.set_volume_export_policy(
                previous['name'],
                policy_name=updated_volume['active_policy_name'])

        # Resize volume
        if 'size_total' in changed_keys:
            log.info("Resizing volume...")
            self.server.resize_volume(volume_name=previous['name'],
                                      new_size=updated_volume['size_total'])

        # Caching policy
        if 'caching_policy' in changed_keys:
            log.info("Setting caching policy...")
            self.server.set_volume_caching_policy(
                volume_name=previous['name'],
                policy_name=updated_volume['caching_policy'])

    def restrict_volume(self, volume_name):
        name = self.parse_volume_name(volume_name)
        self.server.restrict_volume(name)

        for volume in self.server.volumes.filter(name=name):
            return self.format_volume(volume)

# I don't know if this does anything, but it may be necessary for, uh,
# some reason?
# StorageBackend.register(DummyStorage)
