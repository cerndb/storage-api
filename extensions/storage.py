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

from ordered_set import OrderedSet
import cerberus

log = logging.getLogger(__name__)
SCHEMAS = [('volume',
            {'name': {'type': 'string', 'minlength': 1,
                      'required': True},
             'size_used': {'type': 'integer', 'min': 0,
                           'required': True},
             'size_total': {'type': 'integer', 'min': 0,
                            'required': True},
             'filer_address': {'type': 'string', 'minlength': 1,
                               'required': True}})]

cerberus.schema_registry.extend(SCHEMAS)


class ValidationError(Exception):
    pass


def vol_404(volume_name):
    return "No such volume: {}".format(volume_name)


def normalised_with(schema_name, allow_unknown=False):
    """
    A decorator to normalise and validate the return values of a
    function according to a schema.

    Raises a ValidationError if the schema was not correctly validated.
    """

    def validator_decorator(func):
        @functools.wraps(func)
        def inner_wrapper(*args, **kwargs):
            schema = cerberus.schema_registry.get(name=schema_name)
            v = cerberus.Validator(schema, allow_unknown=allow_unknown)
            return_value = func(*args, **kwargs)
            validation_result = v.validate(return_value, normalize=True)
            if not validation_result:
                raise ValidationError(v.errors)  # pragma: no cover
            else:
                return v.normalized(return_value)
        return inner_wrapper
    return validator_decorator


@contextmanager
def annotate_exception(exception, annotation):
    try:
        yield
    except exception:
        raise exception(annotation)


class StorageBackend(metaclass=ABCMeta):

    def __repr__(self):
        return "{}({})".format(type(self).__name__, str(self.__dict__))

    @property
    @abstractmethod
    def volumes():
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

        Raises KeyError if no such volume exists.
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
        - ValueError on poorly formatted data, or invalid data
          entries/attempts to write to read-only fields
        - KeyError if no volume named volume_name exists.
        """
        return NotImplemented

    @abstractmethod
    def create_volume(self, volume_name, **fields):
        """
        Create a new volume with a given name and the provided data
        fields.

        Fields can be at least:
        - size_total

        Raises:
        - ValueError if the data is malformed
        - KeyError if the volume already exists

        Back-ends are allowed to add implementation-specific elements.
        """
        return NotImplemented

    @abstractmethod
    def locks(self, volume_name):
        """
        Return the string naming the host currently holding a lock on
        the volume named volume_name, or None if there were no locks.

        Raises:
        - KeyError if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def create_lock(self, volume_name, host_owner):
        """
        Install a lock held by the host host_owner on the given volume.

        Raises:
        - ValueError if a lock is already held on that volume by another host
        - KeyError if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def remove_lock(self, volume_name, host_owner):
        """
        Remove/break/force the lock on a volume, if held by
        host_owner. Does nothing if no locks were held on volume_name,
        or if the lock wasn't held by host_owner.

        Raises:
        - KeyError if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def policies(self, volume_name):
        """
        Return a list of export policies for the given volume, as a list
        of dictionaries with their associated policies.

        Example:
        ```
        [{
         "policy_name": "my_policy",
         "rules": ["127.0.0.1", "10.10.10.1/24"]
        }]
        ```

        Notably, no policies would yield []. The interpretation
        of these values are up to the implementation, but it can be
        assumed that no policies is not the same thing as a policy with
        no rules.

        Raises:
        - KeyError if no such volume exists
        """
        return NotImplemented

    @abstractmethod
    def get_policy(self, volume_name, policy_name):
        """
        Return a (potentially empty) list of export policies in the form
        of strings representing IP numbers, with possible masks
        associated with the given policy.

        Raises:
        - KeyError if volume_name does not exist or does not have a
          policy named policy_name
        """
        return NotImplemented

    @abstractmethod
    def create_policy(self, volume_name, policy_name, rules):
        """
        Add a new policy with a set of rules to a given volume

        Raises:
        - ValueError if there is already a policy with that name
        - KeyError if there is no such volume
        """
        return NotImplemented

    @abstractmethod
    def remove_policy(self, volume_name, policy_name):
        """
        Remove a policy. After removal, it must be possible to create an
        new policy with the same name.

        Raises:
        - KeyError if no such volume or policy exists
        """

        return NotImplemented

    @abstractmethod
    def clone_volume(self, clone_volume_name,
                     from_volume_name, from_snapshot_name):
        """
        Create a clone of a volume from a provided snapshot.

        Raises:
        - KeyError if no such volume or snapshot exists
        - ValueError if clone_volume_name already exists
        """
        return NotImplemented

    @abstractmethod
    def create_snapshot(self, volume_name, snapshot_name):
        """
        Make a snapshot from the current state of a volume.

        Raises:
        - KeyError if no volume named volume_name exists
        - ValueError if there is already a snapshot named snapshot_name,
          or if the name is invalid.
        """
        return NotImplemented

    @abstractmethod
    def get_snapshot(self, volume_name, snapshot_name):
        """
        Get the data associated with the snapshot.

        FIXME: describe the contents of a snapshot?

        Back-ends are allowed to add additional keys.

        Raises:
        - KeyError if no such volume or snapshot exists
        """

        return NotImplemented

    @abstractmethod
    def delete_snapshot(self, volume_name, snapshot_name):
        """
        Delete, or the closest possible equivalent, a given snapshot.

        Raises:
        - KeyError if no such volume or snapshot exists
        """
        return NotImplemented

    @abstractmethod
    def get_snapshots(self, volume_name):
        """
        Return a list of snapshots for volume_name.

        Raises:
        - KeyError if no such volume exists.
        """
        return NotImplemented

    @abstractmethod
    def rollback_volume(self, volume_name, restore_snapshot_name):
        """
        Roll back a volume to a snapshot.

        Raises:
        - KeyError if volume_name does not exist or does not have a
          snapshot named restore_snapshot_name.
        """
        return NotImplemented

    @abstractmethod
    def ensure_policy_rule_present(self, volume_name, policy_name, rule):
        """
        Idempotently ensure that a given export policy (as represented
        by an IP with optional mask) is present in the rules of a given
        policy. If it is not present it will be added.

        Raises:
        - KeyError if no such volume or policy exists.
        """

        return NotImplemented

    @abstractmethod
    def ensure_policy_rule_absent(self, volume_name, policy_name, rule):
        """
        Idempotently ensure that a given export policy (as represented
        by an IP with optional mask) is absent in the rules of a given
        policy. Will delete it if present, otherwise give no warning.

        Raises:
        - KeyError if no such volume or policy exists.
        """

        return NotImplemented

    def init_app(self, app):
        """
        Initialise a Flask app context with the storage system.

        Example:

        ```
        app = Flask(__name__)
        netapp = NetAppStorage()
        netapp.init_app(app=app)
        ```
        """

        if not hasattr(app, 'extensions'):   # pragma: no coverage
            app.extensions = {}

        class_name = self.__class__.__name__
        app.extensions[class_name] = self


class DummyStorage(StorageBackend):
    def raise_if_volume_absent(self, volume_name):
        """
        Raise a KeyError with an appropriate message if a volume is
        absent.
        """
        if volume_name not in self.vols:
            raise KeyError(vol_404(volume_name))

    def raise_if_snapshot_absent(self, volume_name, snapshot_name):
        """
        Raise a KeyError with an appropriate message if a snapshot is
        absent.

        This implies first running raise_if_volume absent(volume_name).
        """
        self.raise_if_volume_absent(volume_name)

        if snapshot_name not in self.snapshots_store[volume_name]:
            raise KeyError("No such snapshot exists for volume '{}': '{}'"
                           .format(volume_name, snapshot_name))

    def __init__(self):
        self.vols = {}
        self.locks_store = {}
        self.rules_store = {}
        self.snapshots_store = {}

    @property
    def volumes(self):
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

        data = {'name': str(volume_name),
                'size_used': 0,
                'size_total': kwargs.get('size_total', 0),
                'filer_address': kwargs.get('filer_address', "dummy-filer"),
                **kwargs}
        self.vols[volume_name] = data
        self.locks_store.pop(volume_name, None)
        self.rules_store[volume_name] = {}
        self.snapshots_store[volume_name] = {}

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

    def policies(self, volume_name):
        with annotate_exception(KeyError, vol_404(volume_name)):
            return list(self.rules_store[volume_name].values())

    def get_policy(self, volume_name, policy_name):
        self.raise_if_volume_absent(volume_name)

        return self.rules_store[volume_name][policy_name]

    def create_policy(self, volume_name, policy_name, rules):
        log.info("Adding policy {} with rules {} on volume {}"
                 .format(policy_name, rules, volume_name))
        self.raise_if_volume_absent(volume_name)
        self.rules_store[volume_name][policy_name] = list(OrderedSet(rules))

    def remove_policy(self, volume_name, policy_name):
        log.info("Removing policy {} from volume {}"
                 .format(policy_name, volume_name))
        self.raise_if_volume_absent(volume_name)
        self.rules_store[volume_name].pop(policy_name)

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
        self.snapshots_store.pop(snapshot_name)

    def get_snapshots(self, volume_name):
        log.info("Getting snapshots for {}".format(volume_name))
        self.raise_if_volume_absent(volume_name)
        return list(self.snapshots_store.values())

    def rollback_volume(self, volume_name, restore_snapshot_name):
        log.info("Restoring {} to {}"
                 .format(volume_name, restore_snapshot_name))
        self.raise_if_snapshot_absent(volume_name, restore_snapshot_name)

    def ensure_policy_rule_present(self, volume_name, policy_name, rule):
        self.raise_if_volume_absent(volume_name)
        if rule not in self.rules_store[volume_name][policy_name]:
            self.rules_store[volume_name][policy_name].append(rule)

    def ensure_policy_rule_absent(self, volume_name, policy_name, rule):
        self.raise_if_volume_absent(volume_name)
        stored_rules = self.rules_store[volume_name][policy_name]
        self.rules_store[volume_name][policy_name] = list(filter(
            lambda x: x != rule, stored_rules))


StorageBackend.register(DummyStorage)
