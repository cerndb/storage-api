#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.
from storage_api.utils import init_logger

from flask_restplus import Api

from .storage import api as unified_ns
from .introspect import api as introspection_ns
from .common.auth import authorizations

log = init_logger()

__version__ = '3.3.4'
__major_version__ = __version__.split(".")[0]
INTROSPECTION_MOUNTPOINT = "/conf"
SAPI_MOUNTPOINT = "/v{}".format(__major_version__)

api = Api(
    title='CERN Unified Storage API',
    version=__version__,
    description='A unified storage API for all data-storage back-ends.',
    authorizations=authorizations,
    validate=True,
)

api.add_namespace(unified_ns, path=SAPI_MOUNTPOINT)
api.add_namespace(introspection_ns, path=INTROSPECTION_MOUNTPOINT)
