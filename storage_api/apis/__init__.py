#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.
import logging

from flask_restplus import Api

from .storage import api as unified_ns
from .common.auth import authorizations

logging.getLogger(__name__).addHandler(logging.NullHandler())

SAPI_MOUNTPOINT = "/sapi"

__version__ = '3.0.0'

api = Api(
    title='CERN Unified Storage API',
    version=__version__,
    description='A unified storage API for all data-storage back-ends.',
    authorizations=authorizations,
    validate=True,
    default="sapi",
)

api.add_namespace(unified_ns, path=SAPI_MOUNTPOINT)
