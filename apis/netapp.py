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
import apis.common

from flask_restplus import Namespace

api = Namespace('netapp',
                description='Operations on NetApp filers')

apis.common.init_namespace(api, backend_name="DummyStorage")
