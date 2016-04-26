#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from flask import Flask, request
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


class PathREST(Resource):
	logger=None
	def __init__(self):
		''' Method definition '''
		if __name__ == '__main__':
			PathREST.logger = logging.getLogger('storage-api-console')
		else:
			PathREST.logger = logging.getLogger('storage-api')
		
			
	def get(self, path):
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			result=netapp.GetSnapshotsList()
			if result is None:
				StorageRest.logger.debug("we got 0 snapshots")
				return { 'snapshots': 'NONE' }, 200
			PathREST.logger.debug("we got %s snapshots",len(result))
			return  { 'snapshots': result }, 200
	
	def post(self,path):
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		PathREST.logger.debug("path is: %s",spath)
		
		sname=None
		clone=None
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(request.form['snapname'])
			sname=bname.decode('ascii')
			PathREST.logger.debug("new snapshot name is: %s",sname)
		if 'clone' in request.form.keys():
			PathREST.logger.debug("want a clone")
			clone=request.form['clone']
			
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			try:
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


	def delete(self,path):
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		PathREST.logger.debug("path is: %s",spath)
		
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(request.form['snapname'])
			sname=bname.decode('ascii')
		else:
			PathREST.logger.debug("new snapshot name is: %s",sname)
			return { 'snapshot deletion ': 'snapname missing!!' }, 400
		
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			try:
				result=netapp.DeleteSnapshot(sname)
			except Exception as ex:
				PathREST.logger.debug("Exception got error: {0}".format(str(ex)))
				return { 'snapshot deletion ': 'error {0}'.format(str(ex)) }, 400
		
		PathREST.logger.debug("snapshot deleted")
		return { 'snapshot deletion ': 'success' }, 200