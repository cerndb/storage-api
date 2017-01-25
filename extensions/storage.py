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

from utils import OrderedSet

from abc import ABCMeta, abstractmethod
import logging

log = logging.getLogger(__name__)


class StorageBackend(metaclass=ABCMeta):

    @property
    @abstractmethod
    def volumes():
        """
        Return all volumes of the storage backend.

        Read-only property.
        """
        return NotImplemented

    @abstractmethod
    def get_volume(self, name):
        """
        Return a specific volume.

        Raises KeyError if no volume named name exists.
        """
        return NotImplemented

    @abstractmethod
    def create_volume(self, name):
        return NotImplemented

    @abstractmethod
    def create_snapshot(self, volume_name, snapshot_name):
        return NotImplemented

    @abstractmethod
    def delete_snapshot(self, volume_name, snapshot_name):
        return NotImplemented

    @abstractmethod
    def get_snapshots(self, volume_name):
        return NotImplemented

    @abstractmethod
    def get_snapshot(self, volume_name, snapshot_name):
        return NotImplemented

    @abstractmethod
    def clone_volume(self, volume_name, snapshot_name):
        return NotImplemented

    @abstractmethod
    def rollback_volume(self, volume_name, snapshot_name):
        return NotImplemented

    @abstractmethod
    def patch_volume(self, volume_name, data):
        return NotImplemented

    @abstractmethod
    def restrict_volume(self, volume_name):
        """
        Raises KeyError if volume_name is not present.
        """
        return NotImplemented

    @property
    @abstractmethod
    def locks(self):
        return NotImplemented

    @abstractmethod
    def add_lock(self, host):
        return NotImplemented

    @abstractmethod
    def remove_lock(self, host):
        return NotImplemented

    @abstractmethod
    def policies(self, volume):
        return NotImplemented

    @abstractmethod
    def add_policy(self, volume, policy_name, rules):
        return NotImplemented

    @abstractmethod
    def remove_policy(self, volume_name, policy_name):
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

    def __init__(self):
        self.vols = {}
        self.locks_store = {}
        self.rules_store = {}

    @property
    def volumes(self):
        return list(self.vols.values())

    def get_volume(self, path):
        log.info("Trying to get volume {}".format(path))
        return self.vols[path]

    def restrict_volume(self, path):
        log.info("Restricting volume {}".format(path))
        self.vols.pop(path)
        self.locks_store.pop(path, None)
        self.rules_store.pop(path, None)

    def patch_volume(self, volume_name, data):
        log.info("Updating volume {} with data {}"
                 .format(volume_name, data))
        for key in data:
            try:
                self.vols[volume_name][key] = data[key]
            except KeyError as e:
                raise KeyError("No such volume: {}".format(volume_name))

    def create_volume(self, name, **kwargs):
        log.info("Adding new volume '{}': {}"
                 .format(name, str(kwargs)))

        data = {'name': name,
                'locks': [],
                'snapshots': {},
                **kwargs}
        self.vols[name] = data
        self.locks_store.pop(name, None)
        self.rules_store[name] = {}

    def locks(self, volume_name):

        if volume_name not in self.locks_store:
            if volume_name not in self.vols:
                raise KeyError("No such volume: {}".format(volume_name))
            else:
                return []
        else:
            return [{'host': self.locks_store[volume_name]}]

    def add_lock(self, volume_name, host):
        assert volume_name
        assert host

        log.info("Host {} is locking {}".format(host, volume_name))
        if volume_name in self.locks_store and self.locks_store[volume_name] != host:
            raise ValueError("{} is already locked by {}!"
                             .format(volume_name,
                                     self.locks_store[volume_name]))

        self.locks_store[volume_name] = host

    def remove_lock(self, volume_name, host):
        self.locks_store.pop(volume_name)

    def policies(self, volume_name):
        return list(self.rules_store[volume_name].values())

    def get_policy(self, volume_name, policy_name):
        return self.rules_store[volume_name][policy_name]

    def add_policy(self, volume_name, policy_name, rules):
        log.info("Adding policy {} with rules {} on volume {}"
                 .format(policy_name, rules, volume_name))

        if volume_name not in self.vols:
            raise KeyError("No such volume {}".format(volume_name))

        self.rules_store[volume_name][policy_name] = {
            'policy_name': policy_name,
            'rules': list(OrderedSet(rules))}

    def remove_policy(self, volume_name, policy_name):
        log.info("Removing policy {} from volume {}"
                 .format(policy_name, volume_name))

        self.rules_store[volume_name].pop(policy_name)

    def clone_volume(self, name, from_volume_name, from_snapshot_name):
        log.info("Cloning volume {target} from {source}:{snapshot}"
                 .format(target=name, source=from_volume_name,
                         snapshot=from_snapshot_name))
        if name in self.vols:
            raise ValueError("Name already in use!")

        try:
            self.vols[name] = self.vols[from_volume_name]
        except KeyError:
            raise KeyError("Target volume '{}' does not exist"
                           .format(from_volume_name))

    def create_snapshot(self, volume_name, snapshot_name):
        log.info("Creating snapshot {}:{}".format(volume_name, snapshot_name))
        self.vols[volume_name]['snapshots'][snapshot_name] = {'name': snapshot_name}

    def get_snapshot(self, volume_name, snapshot_name):
        log.info("Fetching snapshot {}:{}".format(volume_name, snapshot_name))
        return self.vols[volume_name]['snapshots'][snapshot_name]

    def delete_snapshot(self, volume_name, snapshot_name):
        log.info("Deleting {} on {}".format(snapshot_name, volume_name))
        self.vols[volume_name]['snapshots'].pop(snapshot_name)

    def get_snapshots(self, volume_name):
        log.info("Getting snapshots for {}".format(volume_name))
        return list(self.vols[volume_name]['snapshots'].values())

    def rollback_volume(self, volume_name, restore_snapshot_name):
        log.info("Restoring {} to {}"
                 .format(volume_name, restore_snapshot_name))
        pass

    def policy_rule_present(self, volume_name, policy_name, rule):
        if rule not in self.rules_store[volume_name][policy_name]['rules']:
            self.rules_store[volume_name][policy_name]['rules'].append(rule)

    def policy_rule_absent(self, volume_name, policy_name, rule):
        stored_rules = self.rules_store[volume_name][policy_name]['rules']
        self.rules_store[volume_name][policy_name]['rules'] = list(filter(
            lambda x: x != rule, stored_rules))


StorageBackend.register(DummyStorage)
