#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from flask import Flask, session, request
from flask.ext.restful import Api, Resource
import sys
import re
import logging
import base64
from storage.config import CONFIG
from storage.vendors.BasicStorage import BasicStorage
from storage.vendors.NetAppops import NetAppops
from storage.vendors.NetAppprov import NetAppprov
from storage.vendors.PolicyRulesNetApp import PolicyRulesNetApp
from storage.vendors.StorageException import StorageException


class RulesREST(Resource):
	logger=None
	def __init__(self):
		''' Method definition '''
		if __name__ == '__main__':
			RulesREST.logger = logging.getLogger('storage-api-console')
		else:
			RulesREST.logger = logging.getLogger('storage-api')	
       
	def isrole(role_name):
		def role_decorator(func):
			def role_wrapper(*args,**kwargs):
				if 'user' not in session:
					RulesREST.logger.debug("no user information retrieved, may be not signed up!")
					return { "isrole" : 'no authentication' }, 403
				elif role_name in session['user'].get('Group'):
					return func(*args,**kwargs)
				else:
					RulesREST.logger.debug("no group membership present.")
					return { "isrole" : 'no authentication' }, 403
			return role_wrapper
		return role_decorator
	
	def get(self,path):
		'''Retrieved policy and rules linked to a controller:mountpath tuple'''
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		RulesREST.logger.debug("path is: %s",spath)
		
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			exportpolicy=PolicyRulesNetApp.ExistingVolume(spath)
			try:
				result=exportpolicy.GetRuleAllREST()
			except Exception as ex:
				return { 'rules ops ': 'error: ' + str(ex) }, 500
			else:
				if result is None:
					return { 'rules ops ': 'No rules found' }, 200
				else:
					return { 'rules ops ': 'success ' + str(result) }, 200

	
	@isrole("it-dep-db")
	def put(self,path):
		''' Add or remove an IP on a given existing policy'''
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		RulesREST.logger.debug("path is: %s",spath)
		
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			exportpolicy=PolicyRulesNetApp.ExistingVolume(spath)

		deleterule=None
		addrule=None
		if 'deleterule' in request.form.keys():
			deleterule=base64.urlsafe_b64decode(request.form['deleterule']).decode('ascii')	
		if 'addrule' in request.form.keys():
			addrule=base64.urlsafe_b64decode(request.form['addrule']).decode('ascii')	
		
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			exportpolicy=PolicyRulesNetApp.ExistingVolume(spath)
		
		result=None
		if addrule:
			result=exportpolicy.CreateRuleREST(addrule)
			if result==0:
				return { 'rules ops ': 'success ' + str(addrule) + ' was added.' }, 200
		elif deleterule:
			result=exportpolicy.DeleteRuleREST(deleterule)
			if result==0:
				return { 'rules ops ': 'success ' + str(deleterule) + ' was removed.' }, 200


		return { 'rules ops ': 'noops. Please contact admins'  }, 500
		
		


