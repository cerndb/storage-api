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


class PathREST(Resource):
	logger=None
	def __init__(self):
		''' Method definition '''
		if __name__ == '__main__':
			PathREST.logger = logging.getLogger('storage-api-console')
		else:
			PathREST.logger = logging.getLogger('storage-api')
		self.reqparse = reqparse.RequestParser()
		self.reqparse.add_argument('snapname',type=str, location='form')
		self.reqparse.add_argument('clone',type=int, location='form')

	def isrole(role_name):
		def role_decorator(func):
			def role_wrapper(*args,**kwargs):
				if 'user' not in session:
					PathREST.logger.debug("no user information retrieved, may be not signed up!")
					return { "isrole" : 'no authentication' }, 403
				elif role_name in session['user'].get('Group'):
					return func(*args,**kwargs)
				else:
					PathREST.logger.debug("no group membership present.")
					return { "isrole" : 'no authentication' }, 403
			return role_wrapper
		return role_decorator
	
	def get(self, path):
		'''Retrieve all snapshots if any'''
		try:
			bpath=base64.urlsafe_b64decode(path)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400
	
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			result=netapp.GetSnapshotsList()
			if result is None:
				PathREST.logger.debug("we got 0 snapshots")
				return { 'snapshots': 'NONE' }, 200
			PathREST.logger.debug("we got %s snapshots",len(result))
			return  { 'snapshots': result }, 200
	
	@isrole("it-dep-db")
	def post(self,path):
		'''Creates an snapshot or a clone (if license available in controller). 
			- snapname: base64 encoded name of the snapshot
			- clone: 1 -> clone is created from snapname, 0 no clone just a snapshot to be created
		'''
		args = self.reqparse.parse_args()
		try:
			bpath=base64.urlsafe_b64decode(path)
			spath=bpath.decode('ascii')
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400
		PathREST.logger.debug("path is: %s",spath)
		
		sname=None
		clone=None
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(args['snapname'])
			sname=bname.decode('ascii')
			PathREST.logger.debug("new snapshot name is: %s",sname)
		if 'clone' in request.form.keys():
			PathREST.logger.debug("want a clone")
			clone=args['clone']
		try:	
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400

		if baseclass.GetType() == "NetApp":
			try:	
				netapp=NetAppops(spath)
				if sname is None:
					if clone:
						PathREST.logger.debug("1")
						return { 'snapshot_clone creation ': 'No snapshot provided for clonning'}, 400 
					else:
						result=netapp.CreateSnapshot()
				else:
					PathREST.logger.debug("2")
					if clone:
						result=netapp.CloneSnapshot(sname)
					else:
						result=netapp.CreateSnapshot(sname)
			except Exception as ex:
				PathREST.logger.debug("Exception taken: %s",str(ex))
				return { 'snapshot_clone creation ': 'error ' + str(ex) }, 500

			PathREST.logger.debug("snapshot_clone created")
			if result==0: 
				return { 'snapshot_clone creation ': 'success' }, 200
			if len(result) > 1:
				return { 'snapshot_clone creation ': 'success - junction-path:' + result }, 200


	@isrole("it-dep-db")
	def delete(self,path):
		'''Delete a given snapshot'''
		args = self.reqparse.parse_args()
		try:
			bpath=base64.urlsafe_b64decode(path)
			spath=bpath.decode('ascii')
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400
		PathREST.logger.debug("path is: %s",spath)
		
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(args['snapname'])
			sname=bname.decode('ascii')
		else:
			PathREST.logger.debug("new snapshot name is: %s",sname)
			return { 'snapshot deletion ': 'snapname missing!!' }, 400

		try:		
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			try:
				result=netapp.DeleteSnapshot(sname)
			except Exception as ex:
				PathREST.logger.debug("Exception got error: {0}".format(str(ex)))
				return { 'snapshot deletion ': 'error {0}'.format(str(ex)) }, 400
		
		PathREST.logger.debug("snapshot deleted")
		return { 'snapshot deletion ': 'success' }, 200