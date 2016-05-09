#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import sys

activate_this = '/ORA/dbs01/work/storage-api/v1/bin/activate_this.py'
#execfile(activate_this, dict(__file__=activate_this))

#exec(open("/ORA/dbs01/work/storage-api/v1/bin/activate_this.py").read())
with open(activate_this) as f:
    code = compile(f.read(), activate_this, 'exec')
    exec(code, dict(__file__=activate_this))


# Ensure there is an app.py script in the current folder
from storage.api.handlers import app as application 
