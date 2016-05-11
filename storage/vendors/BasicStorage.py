#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import re
import logging
import sys
import ssl
from storage.config import CONFIG

class BasicStorage(object):
	logger=None
	def __init__(self,serverpath):
		# Get logger singleton
		
		if __name__ == '__main__':
			BasicStorage.logger = logging.getLogger('storage-api-console')
		else:
			BasicStorage.logger = logging.getLogger('storage-api')
		BasicStorage.logger.debug("Begin")
		BasicStorage.logger.debug("logger has been initialised")
		self.serverpath=serverpath
		self.controller = None
		self.serverlayout = None
		self.volume = {}
		self.type = None
		self.clustertoconnect = None

		ssl._create_default_https_context = ssl._create_unverified_context

		BasicStorage.logger.debug("Begin")
		assert serverpath.count(':') == 1 , "too many <:> in the tuple controller serverpath, this is an error"
			
		self.controller,self.serverlayout = serverpath.split(':',2)
		BasicStorage.logger.debug("logger has been initialised: controller: <%s> controllers path: <%s>",self.controller,self.serverlayout)
		helper = re.compile(r'^(\D{6,})\d{1,}.*$')
		self.clustertoconnect=helper.search(self.controller).groups()  #Exception: AttributeError: 'NoneType' object has no attribute 'groups'
		assert len(self.clustertoconnect) >= 1, "we couldnt extract which cluster are you working with: %s" % self.controller

		BasicStorage.logger.debug("serverlayout is: " + self.serverlayout)
		assert re.search('^[/\-\w]+$',self.serverlayout), "remote path contains strange characters"
		if CONFIG[self.clustertoconnect[0]]["type"]:
			self.type = CONFIG[self.clustertoconnect[0]]["type"]
			BasicStorage.logger.debug("It's a %s instance",self.type)
		BasicStorage.logger.debug("End")


	def GetType(self):
		BasicStorage.logger.debug("Begin")
		BasicStorage.logger.debug("End")
		return self.type

