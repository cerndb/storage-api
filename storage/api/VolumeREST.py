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
import sys,traceback
import re
import logging
import base64
from storage.config import CONFIG
from storage.vendors.BasicStorage import BasicStorage
from storage.vendors.NetAppops import NetAppops
from storage.vendors.NetAppprov import NetAppprov
from storage.vendors.PolicyRulesNetApp import PolicyRulesNetApp
from storage.vendors.StorageException import StorageException


class VolumeREST(Resource):
	logger=None
	def __init__(self):
		''' Method definition '''
		if __name__ == '__main__':
			VolumeREST.logger = logging.getLogger('storage-api-console')
		else:
			VolumeREST.logger = logging.getLogger('storage-api')	
		self.reqparse_post = reqparse.RequestParser(bundle_errors=True)
		self.reqparse_post.add_argument('vendor',type=str, location='form',required=True)
		self.reqparse_post.add_argument('clustername',type=str, location='form',required=True)
		self.reqparse_post.add_argument('initsize',type=int, location='form',required=True)
		self.reqparse_post.add_argument('maximumsize',type=int, location='form',required=True)
		self.reqparse_post.add_argument('incrementsize',type=int, location='form',required=True)
		self.reqparse_post.add_argument('vserver',type=str, location='form',required=True)
		self.reqparse_post.add_argument('policy',type=str, location='form',required=True)
		self.reqparse_post.add_argument('junctionpath',type=str, location='form',required=True)
		self.reqparse_post.add_argument('typeaggr',type=str, location='form',required=True)
		self.reqparse_post.add_argument('snapenable',type=int, location='form',default=1)
		self.reqparse_post.add_argument('ip',type=str, location='form',default=0)
		self.reqparse_post.add_argument('business',type=str, location='form',default=0)
		self.reqparse_delete=reqparse.RequestParser()
		self.reqparse_delete.add_argument('clone',type=int,default=0)
		self.reqparse_put=reqparse.RequestParser()
		self.reqparse_put.add_argument('maxautosize',type=int,required=True)
		self.reqparse_put.add_argument('increment',type=int,default=0)

		
      
	def isrole(role_name):
		def role_decorator(func):
			def role_wrapper(*args,**kwargs):
				if 'user' not in session:
					VolumeREST.logger.debug("no user information retrieved, may be not signed up!")
					return { "isrole" : 'no authentication' }, 403
				elif role_name in session['user'].get('Group').split(';'):
					return func(*args,**kwargs)
				else:
					VolumeREST.logger.debug("no group membership present.")
					return { "isrole" : 'no authentication' }, 403
			return role_wrapper
		return role_decorator

	def get(self,volname):	
		'''Retrieve information of a given volume represented by its mount path at the server. In case there are snapshots available those are also retrieved.
			volname is coded in base64. 	
		'''
		try:
			bpath=base64.urlsafe_b64decode(volname)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400

		VolumeREST.logger.debug("path is: %s",spath)
		
		if baseclass.GetType() == "NetApp":
			netapp=NetAppprov.ExistingVol(spath)
			if not isinstance(netapp,(BasicStorage,NetAppprov)):
				return { 'volume get ': 'error no online volume found' }, 500
			try:
				result=netapp.GetInfoPath()
			except Exception as ex:
				VolumeREST.logger.debug('problem getting volume information' + str(ex))
				return { 'volume get ': 'error ' + str(ex) }, 500
			else:
				if int(result['snap_reserved']) > 0 :
					netapp2=NetAppops(spath)
					snaps=netapp2.GetSnapshotsList()
					if snaps and len(snaps) > 0 :
						 return { 'volume get ': 'success ' + str(result) + "snaps list: " + str(snaps) }, 20	
				return { 'volume get ': 'success ' + str(result) }, 200	


	@isrole("it-dep-db")		
	def post(self,volname):
		'''Creation of a new volume.  Some parameters are required:
			-volname
			-clustername e.g. dbnasc
			-initsize: initial size in GB
			-maximumsize: maximum autosize in GB
			-incrementsize: in GB
			-policy: name of the export policy assigned to the volume
			-junctionpath: NFS server access path. Base64 encoded.
			-typeaggr: e.g. hdd-aggr, ssd-aggr, hybrid-aggr
			-snapsenable: 1 -> yes, 0-> no
			-ip: IP. Base64 encoded. 
			-business: e.g. dbod
			-vendor: NetApp, PureStorage, Ceph
		'''
		#'dbnasc','toTo',1,100,1,'vs2sx50','kk','/ORA/dbs00/TOTO','hdd-aggr',1,'199.22.22.22',"dbod"
		args = self.reqparse_post.parse_args()
		vendor=args['vendor']
		VolumeREST.logger.debug('vendor is: ' + vendor)
		clustername=args['clustername']
		if not volname:
			return { 'volume creation ': 'error: missing parameter volname' }, 400
		else:
			VolumeREST.logger.debug('volname is: ' + volname)
		initsize=args['initsize']
		VolumeREST.logger.debug('maximumsize is:' + str(initsize))
		maximumsize=request.form['maximumsize']
		VolumeREST.logger.debug('maximumsize is:' + str(maximumsize))
		incrementsize=request.form['incrementsize']
		VolumeREST.logger.debug('incrementsize is:' + str(incrementsize))
		vserver=args['vserver']
		VolumeREST.logger.debug('vserver is:' + vserver)
		policy=args['policy']
		VolumeREST.logger.debug('policy is:' + policy)
		junctionpath=base64.urlsafe_b64decode(args['junctionpath']).decode('ascii')
		VolumeREST.logger.debug('junctionpath is:' + junctionpath)
		typeaggr=args['typeaggr']
		VolumeREST.logger.debug('typeaggr is:' + typeaggr)
		snapenable=args['snapenable']
		VolumeREST.logger.debug('snapenable is:' + str(snapenable))
		ip=base64.urlsafe_b64decode(args['ip']).decode('ascii')
		VolumeREST.logger.debug('ip is:' + str(ip))
		business=args['business']
		VolumeREST.logger.debug('business is:' + str(business))
		
		if vendor == 'NetApp':
			try:
				netapp=NetAppprov(clustername,volname,initsize,maximumsize,incrementsize,vserver,policy,junctionpath,typeaggr,ip,snapenable,business)
				result=netapp.CreateVolume()
			except Exception as ex:
				exc_type, exc_value, exc_traceback = sys.exc_info()
				VolumeREST.logger.debug('problem creating volume : ' + str(ex))
				VolumeREST.logger.debug('problem creating volume : ' + repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
				return { 'volume creation ': 'error ' + str(ex) }, 500
			else:
				if (result==0):
					VolumeREST.logger.debug('Volume %s has been created',volname)
					return { 'volume creation ': 'success' }, 200
				else:
					VolumeREST.logger.debug('Volume %s has failed',volname)
					return { 'volume creation ': 'error creating' + volname }, 500

		else:
			return { 'volume creation ': 'wrong vendor' }, 400




	@isrole("it-db-storage")		
	def delete(self,volname):
		''' Deletes a volume. It's represented by its junction path and IP to mount.
			If clone form variable is present, the volume is removed, otherwise is set in restricted mode (NetApp).
		'''
		try:
			bpath=base64.urlsafe_b64decode(volname)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400

		VolumeREST.logger.debug("path is: %s",spath)
		args = self.reqparse_delete.parse_args()
		clone=args['clone']

		if baseclass.GetType() == "NetApp":
			netapp=NetAppprov.ExistingVol(spath)
			if not isinstance(netapp,(BasicStorage,NetAppprov)):
				return { 'volume deletion ': 'error no online volume found' }, 500
			try:
				if clone:
					result=netapp.DeleteVolume()
				else:
					result=netapp.RestrictVolume()
			except Exception as ex:
				VolumeREST.logger.debug('problem deleting volume' + str(ex))
				return { 'volume deletion ': 'error ' + str(ex) }, 500
			else:
				if (result==0):
					VolumeREST.logger.debug('Volume %s has been deleted/restricted',netapp.volname)
					return { 'volume deletion ': 'success' }, 200
				else:
					VolumeREST.logger.debug('Volume %s deletion/restriction has failed',netapp.volname)
					return { 'volume deletion ': 'error deleting' + netapp.volname }, 500

		else:
			return { 'volume deletion/restriction ': 'wrong vendor' }, 400
		
	
	@isrole("it-dep-db")
	def put(self, volname):
		'''Modify autosize. Values should be provided on GB. You can modify maximum autosize and increment'''
		try:
			bpath=base64.urlsafe_b64decode(volname)
			spath=bpath.decode('ascii')
			baseclass=BasicStorage(spath)
		except Exception as ex:
			return { 'get': 'wrong format ' + str(ex) }, 400
		VolumeREST.logger.debug("path is: %s",spath)
		
		args=self.reqparse_put.parse_args()
		maxautosize=args['maxautosize']
		increment=args['increment']
		
		if baseclass.GetType() == "NetApp":
			netapp=NetAppprov.ExistingVol(spath)
			if not isinstance(netapp,(BasicStorage,NetAppprov)):
				return { 'volume setautosize ': 'error no online volume found' }, 500
			
			result=netapp.SetAutoSize(maxautosize,increment)	
			if result==0:
				VolumeREST.logger.debug('autosize [%s,%s] has been set for %s',maxautosize,increment,netapp.volname)
				return { 'volume setautosize ': 'success' }, 200
			else:
				VolumeREST.logger.debug('autosize couldnt be set for volume: %s',netapp.volname)
				return { 'volume setautosize ': 'error: ' + result }, 500

		

