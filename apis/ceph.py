# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import apis.common

from flask_restplus import Namespace

api = Namespace('ceph', description='Operations on Ceph')
apis.common.init_namespace(api, backend_name="DummyStorage")
