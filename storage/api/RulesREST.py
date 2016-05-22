#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from flask import Flask, session, request
from flask.ext.restful import Api, Resource, reqparse
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
		self.reqparse_put = reqparse.RequestParser(bundle_errors=True)
		self.reqparse_put.add_argument('addrule',type=str, location='form')
		self.reqparse_put.add_argument('deleterule',type=str, location='form')

	def isrole(role_name):
		def role_decorator(func):
			def role_wrapper(*args,**kwargs):
				if 'user' not in session:
					RulesREST.logger.debug("no user information retrieved, may be not signed up!")
					return { "isrole" : 'no authentication' }, 403
				elif role_name in session['user'].get('Group').split(';'):
					return func(*args,**kwargs)
				else:
					RulesREST.logger.debug("no group membership present.")
					return { "isrole" : 'no authentication' }, 403
			return role_wrapper
		return role_decorator
	
	def get(self,path):
		'''Retrieved policy and rules linked to a controller:mountpath tuple. Path provided in base64 coding.'''
		try:
			bpath=base64.urlsafe_b64decode(path)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400


		RulesREST.logger.debug("path is: %s",spath)
		
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
		''' Add or remove an IP on a given existing policy. IP provided in base64 coding.
			-addrule: to add an IP
			-deleterule: to delete an IP
		IP should be an IPv4 IP.
		'''
		deleterule=None
		addrule=None
		try:
			bpath=base64.urlsafe_b64decode(path)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
			RulesREST.logger.debug("path is: %s",spath)
		
			args = self.reqparse_put.parse_args()
			if 'deleterule' in request.form.keys():
				deleterule=base64.urlsafe_b64decode(args['deleterule']).decode('ascii')	
				assert re.search('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',deleterule), "Please provide an IPv4"
			if 'addrule' in request.form.keys():
				addrule=base64.urlsafe_b64decode(args['addrule']).decode('ascii')
				assert re.search('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',deleterule), "Please provide an IPv4"
			if not (addrule or delete):
				return { 'put': 'please provide either deleterule or addrule'}, 400
			

		except Exception as ex:
			return { 'put': 'wrong format ' + str(ex) }, 400
		
		
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
		
		


