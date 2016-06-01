#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging
import logging.config
import sys, traceback
import json


CONFIG = {}

try: 
	with open('/etc/storage/logging.conf') as jdata:
	    	config_logging = json.load(jdata)

	logging.config.dictConfig(config_logging)
	logger = logging.getLogger('storage-api')

	logger.debug("logger has been initialised")
	
	with open('/etc/storage/storage.conf') as jdataf:
    		CONFIG = json.load(jdataf)
	
	
except IOError as e:
    traceback.print_exc(file=sys.stdout)
    sys.exit(e.code)