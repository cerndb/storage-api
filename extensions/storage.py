# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

"""
This is a generalised back-end for storage systems.
"""
from abc import ABCMeta, abstractmethod

from flask import current_app


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
    def restrict_volume(self, volume_name):
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

    @property
    @abstractmethod
    def rules(self):
        return NotImplemented

    @abstractmethod
    def add_rule(self, rule):
        return NotImplemented

    @abstractmethod
    def remove_rule(self, rule):
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

        if not hasattr(app, 'extensions'):
            app.extensions = {}

        class_name = self.__class__.__name__
        app.extensions[class_name] = self


class DummyStorage(StorageBackend):

    vols = {}
    locks_store = []
    rules_store = []

    @property
    def volumes(self):
        return list(self.vols.values())

    def get_volume(self, path):
        return self.vols[path]

    def restrict_volume(self, path):
        self.vols.pop(path)

    def create_volume(self, name, **kwargs):
        data = {'name': name,
                'locks': [],
                'snapshots': [],
                **kwargs}
        self.vols[name] = data
        current_app.logger.info("Current volume data is: {}"
                                .format(str(self.vols)))

    @property
    def locks(self):
        return self.locks_store

    def add_lock():
        pass

    def remove_lock():
        pass

    @property
    def rules():
        pass

    def add_rule():
        pass

    def remove_rule():
        pass

    def clone_volume(self, name, from_volume_name, from_snapshot_name):
        if name in self.vols:
            raise ValueError("Name already in use!")

    def get_snapshot():
        pass

    def get_snapshots():
        pass

    def rollback_volume():
        pass


StorageBackend.register(DummyStorage)
