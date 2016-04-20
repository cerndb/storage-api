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
from storage.vendors.StorageException import StorageException

app = Flask(__name__)
api = Api(app)

class StorageREST(Resource):
	logger=None
	def __init__(self):
		''' Method definition '''
		if __name__ == '__main__':
			StorageREST.logger = logging.getLogger('storage-api-console')
		else:
			StorageREST.logger = logging.getLogger('storage-api')
		
			
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
			StorageREST.logger.debug("we got %s snapshots",len(result))
			return  { 'snapshots': result }, 200
	
	def post(self,path):
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		StorageREST.logger.debug("path is: %s",spath)
		
		sname=None
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(request.form['snapname'])
			sname=bname.decode('ascii')
			StorageREST.logger.debug("new snapshot name is: %s",sname)

		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			try:
				if sname is None:
					result=netapp.CreateSnapshot()
				else:
					result=netapp.CreateSnapshot(sname)
			except Exception:
				StorageREST.logger.debug("Exception taken: %s",sys.exc_info()[0])
				return { 'snapshot creation ': 'error {0}'.format(sys.exc_info()[0]) }, 400

			StorageREST.logger.debug("snapshot created")
			return { 'snapshot creation ': 'success' }, 200

	def delete(self,path):
		bpath=base64.urlsafe_b64decode(path)
		spath=bpath.decode('ascii')
		StorageREST.logger.debug("path is: %s",spath)
		
		if 'snapname' in request.form.keys():
			bname=base64.urlsafe_b64decode(request.form['snapname'])
			sname=bname.decode('ascii')
		else:
			StorageREST.logger.debug("new snapshot name is: %s",sname)
			return { 'snapshot deletion ': 'snapname missing!!' }, 400
		
		baseclass=BasicStorage(spath)
		if baseclass.GetType() == "NetApp":
			netapp=NetAppops(spath)
			try:
				result=netapp.DeleteSnapshot(sname)
			except Exception as ex:
				StorageREST.logger.debug("Exception got error: {0}".format(str(ex)))
				return { 'snapshot deletion ': 'error {0}'.format(str(ex)) }, 400
		
		StorageREST.logger.debug("snapshot deleted")
		return { 'snapshot deletion ': 'success' }, 200

		

       	

api.add_resource(StorageREST, '/storage/api/v1.0/paths/<string:path>')
if __name__ == '__main__':
    app.run(debug=True)