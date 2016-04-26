#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import json
import sys
import re
import time
import logging
from storage.config import CONFIG
sys.path.append("/ORA/dbs01/work/storage-api/lib/python/NetApp")
from NaServer import *
from storage.vendors.BasicStorage import BasicStorage
from storage.vendors.StorageException import StorageException



class NetAppops(BasicStorage):
	def __init__(self,serverpath):
		BasicStorage.__init__(self,serverpath)
		if __name__ == '__main__':
			BasicStorage.logger = logging.getLogger('storage-api-console')
		else:
			BasicStorage.logger = logging.getLogger('storage-api')
		NetAppops.logger.debug("Begin")
		self.user = None
		self.pwd = None
		self.server_zapi = None

		NetAppops.logger.debug("End")


			
	def CreateServer(self,clustername,vserver=0):
		# Find controller and controller's path
		NetAppops.logger.debug("Begin")
 
		if vserver != 0:
			NetAppops.logger.debug("working with IP: %s and user: %s", CONFIG[clustername][vserver]['mgmt-ip'], CONFIG[clustername][vserver]['admin'])
			s = NaServer(CONFIG[clustername][vserver]['mgmt-ip'], 1, int(CONFIG[clustername]['zapivers']))
			self.user = CONFIG[clustername][vserver]['admin']
			self.pwd = CONFIG[clustername][vserver]['admin-pwd']
		else:
			NetAppops.logger.debug("working with IP: %s and user: %s", CONFIG[clustername]['mgmt-ip'], CONFIG[clustername]['admin'])
			s = NaServer(CONFIG[clustername]['mgmt-ip'], 1, int(CONFIG[clustername]['zapivers']))
			self.user = CONFIG[clustername]['admin']
			self.pwd = CONFIG[clustername]['admin-pwd']
			

		resp = s.set_style('LOGIN')
		if (resp and resp.results_errno() != 0) :
			r = resp.results_reason()
			NetAppops.logger.error("setting logging failed %s .", r)
			raise StorageException("problems setting login style: %s", r)
		
		if (resp and resp.results_errno() != 0) :
			r = resp.results_reason()
			NetAppops.logger.error("setting port failed %s .", r)
			raise StorageException("problems setting port failed: %s", r)

		resp=s.set_admin_user(self.user, self.pwd)
		if (resp and resp.results_errno() != 0) :
			r = resp.results_reason()
			BasicStorage.logger.error("setting credentials failed %s .", r)
			raise StorageException("problems setting credentials failed: %s", r)
	
		s.set_port(443)
		resp = s.set_transport_type('HTTPS')
		if (resp and resp.results_errno() != 0) :
			r = resp.results_reason()
			BasicStorage.logger.error("setting logging failed %s .", r)
			raise StorageException("problems setting login style: %s", r)
		if self.volume:
			BasicStorage.logger.debug("volume dictionary: %s",self.volume)	
		if 'vserver' in self.volume and (vserver != 0):
			BasicStorage.logger.debug("vserver value: %s",self.volume["vserver"])
			resp=s.set_vserver(self.volume["vserver"])
			#if (resp and resp.results_errno() != 0) :
			#	r = resp.results_reason()
			#	BasicStorage.logger.error("setting vserver failed %s .", r)
			#	raise StorageException("problems setting vserver: %s", r)
		
		if vserver != 0:
			self.server_zapi=s
		NetAppops.logger.error("server ZAPI has been created")
		NetAppops.logger.debug("End")
		#print("Server cert verification: ",s.is_server_cert_verification_enabled())
		#print("hostname  verification: ",s.is_hostname_verification_enabled())

		return s

	def GetVserver(self):
		NetAppops.logger.debug("begin")
		if self.server_zapi is None:
			if len(self.volume) ==0 or 'vserver' not in self.volume.keys():
				self.GetInfoPath()
			self.CreateServer(self.clustertoconnect[0],self.volume['vserver'])
		NetAppops.logger.debug("end")

		
	def GetInfoPath(self, admin=1):
		'''It's supposed to just retrieved one volume.'''

		NetAppops.logger.debug("begin")
		s=self.CreateServer(self.clustertoconnect[0])
			
		tag=None
		while True:
			#build query
			api1 = NaElement("volume-get-iter")
			if tag is not None: 
				api1.child_add_string("tag",tag);
			api1.child_add_string("max-records",10);
			query = NaElement("query")
			
			
			volpath_parent = NaElement("volume-attributes")
			volpath = NaElement("volume-id-attributes")
			volpath.child_add_string("junction-path",self.serverlayout)
			self.volume["junction-path"]=self.serverlayout

			query.child_add(volpath_parent)
			volpath_parent.child_add(volpath)		
			api1.child_add(query)
			#print(api1.sprintf())		
			#Get attributes we want
			desiredAttrs = NaElement("desired-attributes")
			desiredAutoSpace = NaElement("volume-autosize-attributes")
			desiredIdAttr = NaElement("volume-id-attributes")
			desiredSpace = NaElement("volume-space-attributes")
			desiredState = NaElement("volume-state-attributes")
			desiredExport = NaElement("volume-export-attributes")
			#desiredExport.child_add_string("policy","")

			desiredAttrs.child_add(desiredAutoSpace)
			desiredAttrs.child_add(desiredIdAttr)
			desiredAttrs.child_add(desiredSpace)
			desiredAttrs.child_add(desiredState)
			desiredAttrs.child_add(desiredExport)
			api1.child_add(desiredAttrs)
			
			NetAppops.logger.debug("query looks like: %s",api1.sprintf())

			resp=s.invoke_elem(api1)
			if isinstance(resp,NaElement) and resp.results_errno() != 0:
				NetAppops.logger.error("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
				raise StorageException("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())

			if isinstance(resp,NaElement) and resp.child_get_int("num-records")== 0:
				NetAppops.logger.error("query returned 0 records.")
				raise StorageException("query returned 0 records.")

			if isinstance(resp,NaElement) and resp.child_get_int("num-records") > 1:
				NetAppops.logger.error("query returned %s records, when just one is expected.", resp.child_get_int("num-records"))
				raise StorageException("query returned %s records, when just one is expected.", resp.child_get_int("num-records"))

			volist = resp.child_get("attributes-list").children_get()
			v_name=v_aggregate=v_vserver=v_autosizeon=v_state=None
			v_total_size=0
			v_used_size=0
			v_snap_percentage=0
			for v in volist:
				v_attrs=v.child_get("volume-id-attributes")
				if v_attrs:
					v_name=v_attrs.child_get_string("name") 
					self.volume["name"] = v_name
					v_aggregate=v_attrs.child_get_string("containing-aggregate-name")
					self.volume["aggregate"]=v_aggregate
					v_vserver=v_attrs.child_get_string("owning-vserver-name")
					self.volume["vserver"]=v_vserver

				v_size_attrs=v.child_get("volume-space-attributes")
				if v_size_attrs:
					v_total_size=v_size_attrs.child_get_string("size-total")
					self.volume["total_size"]=v_total_size
					v_used_size=v_size_attrs.child_get_string("size-used")
					self.volume["used_size"]=v_used_size
					v_snap_percentage=v_size_attrs.child_get_string("percentage-snapshot-reserve")
					self.volume["snap_reserved"]=v_snap_percentage

				v_autosize_attrs=v.child_get("volume-autosize-attributes")
				if v_autosize_attrs:
					v_autosizeon=v_autosize_attrs.child_get_string("is-enabled")
					self.volume["autosizeon"]=v_autosizeon
					if v_autosizeon:
						v_autosizemax=v_autosize_attrs.child_get_string("maximum-size")
						self.volume["autosizemax"]=v_autosizemax
						v_autoincrement=v_autosize_attrs.child_get_string("increment-size")
						self.volume["autoincrement"]=v_autoincrement

				v_state_attrs = v.child_get("volume-state-attributes")
				if v_state_attrs:	
					v_state=v_state_attrs.child_get_string("state")
					self.volume["state"]=v_state

				v_export_attrs = v.child_get("volume-export-attributes")
				if v_export_attrs:	
					v_policy=v_export_attrs.child_get_string("policy")
					self.volume["policy"]=v_policy
			
			tag=None #resp.child_get("next-tag")
			break # we only want first iteraction	
			
		NetAppops.logger.debug("metadata about the volume: %s",self.volume)		
		

		NetAppops.logger.debug("end")
		return self.volume

	def GetInfoVolandAggr(self):
		''' '''
		NetAppops.logger.debug("begin")
		if not self.volume:
			self.GetInfoPath()
		
		api1=NaElement("aggr-get-iter")
		# We expect just one element
		api1.child_add_string("max-records",10)
		query = NaElement("query")
		aggr_parent=NaElement("aggr-attributes")
		query.child_add(aggr_parent)
		aggr_parent.child_add_string("aggregate-name",self.volume["aggregate"])
		api1.child_add(query)
		desiredAttrs=NaElement("desired-attributes")
		desiredSpace=NaElement("aggr-space-attributes")
		nodeid=NaElement("aggr-ownership-attributes")
		desiredAttrs.child_add(desiredSpace)
		desiredAttrs.child_add(nodeid)
		api1.child_add(desiredAttrs)

		NetAppops.logger.debug("query looks like: %s",api1.sprintf())

		s=self.CreateServer(self.clustertoconnect[0])
		resp=s.invoke_elem(api1)
		
		if isinstance(resp,NaElement) and resp.results_errno() != 0:
			NetAppops.logger.error("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
			raise StorageException("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())

		if isinstance(resp,NaElement) and resp.child_get_int("num-records")== 0:
				NetAppops.logger.error("query returned 0 records.")
				raise StorageException("query returned 0 records.")

		aggrList=resp.child_get("attributes-list").children_get()
		for aggrInfo in aggrList:
			aggrSizeAttrs=aggrInfo.child_get("aggr-space-attributes")
			if aggrSizeAttrs:
				aggrusedsize=aggrSizeAttrs.child_get_string("size-used")
				aggrfreesize=aggrSizeAttrs.child_get_string("size-available")
			nodeidinfo=aggrInfo.child_get("aggr-ownership-attributes")
			if nodeidinfo:
				nodename=nodeidinfo.child_get_string("owner-name")
			
		
		aggrVol={ "aggr_name": self.volume["aggregate"], "aggr_size_used" : aggrusedsize, "aggr_size_free" : aggrfreesize  }
		self.volume["aggregate"]=aggrVol
		
		NetAppops.logger.debug("metadata about the aggregate: %s",aggrVol)
		
		NetAppops.logger.debug("end")
		return self.volume

	def GetSnapshotsList(self):
		'''List all snapshots linked to a path'''
		NetAppops.logger.debug("begin")

		self.GetVserver()
		
		resp=self.server_zapi.invoke("snapshot-list-info", "volume", self.volume["name"])
		if isinstance(resp,NaElement) and resp.results_errno() != 0:
			NetAppops.logger.error("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
			raise StorageException("query failed: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
	
		snapshots = resp.child_get("snapshots");		
		if ((snapshots == None) or (snapshots == "")):
			NetAppops.logger.error("No snapshots were retrieved")
			return None
		snapshotsList = snapshots.children_get()	
		snaps=[]
		for ss in snapshotsList:
			accesstime = float(ss.child_get_int("access-time"))
			total = ss.child_get_int("total")
			cumtotal =   ss.child_get_int("cumulative-total")
			busy = (ss.child_get_string("busy") == "true")
			dependency = ss.child_get_string("dependency")
			name = ss.child_get_string("name")
			date = time.localtime(accesstime)
			snaps.append('{:>23} {:>24} {} {:>10} {:>10} {:>10}'.format(name, time.strftime("%Y%m%d_%H%M%S", date), busy, total, cumtotal, dependency))

			
		NetAppops.logger.debug("snaps retrieved for volume %s: %s",self.volume["name"],snaps)
		NetAppops.logger.debug("end")
		return snaps

	def CreateSnapshot(self,name=0):
		'''It creates a snapshot with the name provided, if any'''
		NetAppops.logger.debug("begin")
		if name==0:
			name='snapscript_{}'.format(time.strftime("%d%m%Y_%H%M%S", time.gmtime()))
			NetAppops.logger.debug("snap name %s",name)
		self.GetVserver()	
		resp = self.server_zapi.invoke("snapshot-create","volume", self.volume["name"],"snapshot", name)
		if (resp.results_errno() != 0):	
			NetAppops.logger.error("while creating an snapshot: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
			raise StorageException("while creating an snapshot: reason %s error number: %s ", resp.results_reason(),resp.results_errno())
		NetAppops.logger.debug("snapshot %s created",name)
		NetAppops.logger.debug("end")
		return 0

	def RestoreSnapshot(self,name):
		'''It restores an snapshot on our instance volume'''
		NetAppops.logger.debug("begin")
		if name is None:
			NetAppops.logger.error("an snapshot needs to be provided")
			raise StorageException("an snapshot needs to be provided")
		self.GetVserver()	
		resp = self.server_zapi.invoke("snapshot-restore-volume","volume", self.volume["name"],"snapshot", name)
		if (resp.results_errno() != 0):	
			NetAppops.logger.error("while restoring snapshot %s on volume %s: reason %s error number: %s ", name, self.volume["name"],resp.results_reason(),resp.results_errno())
			raise StorageException("while restoring  snapshot %s on volume %s: reason %s error number: %s ",name, self.volume["name"],resp.results_reason(),resp.results_errno())
		NetAppops.logger.debug("snapshot %s restored",name)
		NetAppops.logger.debug("end")
		return 0
	
	def CloneSnapshot(self,snapshot=0,junction_path=0):
		'''Create a clone. License is requrired.'''
		NetAppops.logger.debug("begin")
		appendstr='_{}'.format(time.strftime("%d%m%Y_%H%M%S", time.gmtime()))	
		if 'name' not in self.volume:
			self.GetInfoPath(0)
		volname = self.volume["name"] + appendstr + 'clone'
		NetAppops.logger.debug("volname is: %s",volname)
		if not junction_path:
			junction_path=self.volume["junction-path"] + appendstr
		
		NetAppops.logger.debug("junction-path: %s",junction_path)
		api=NaElement('volume-clone-create')
		api.child_add_string('junction-active','true')
		api.child_add_string('junction-path',junction_path)
		api.child_add_string('volume',volname)
		api.child_add_string('parent-volume',self.volume["name"])
		if not snapshot:
			api.child_add_string('parent-snapshot',snapshot)

		self.GetVserver()	
		resp = self.server_zapi.invoke_elem(api)
		if (resp.results_errno() != 0):	
			NetAppops.logger.error("while cloning snapshot %s on volume %s: reason %s error number: %s ", snapshot, self.volume["name"],resp.results_reason(),resp.results_errno())
			raise StorageException("while cloning snapshot %s on volume %s: reason %s error number: %s ",snapshot, self.volume["name"],resp.results_reason(),resp.results_errno())

		NetAppops.logger.debug("Cloned successfully")
		NetAppops.logger.debug("end")
		return junction_path

	def DeleteSnapshot(self,name):
		'''It deletes an snapshot on our instance volume'''
		NetAppops.logger.debug("begin")
		if name is None:
			NetAppops.logger.error("an snapshot needs to be provided")
			raise StorageException("an snapshot needs to be provided")
		self.GetVserver()	
		resp = self.server_zapi.invoke("snapshot-delete","volume", self.volume["name"],"snapshot", name)
		if (resp.results_errno() != 0):	
			NetAppops.logger.error("while deleting snapshot %s on volume %s: reason %s error number: %s ", name, self.volume["name"],resp.results_reason(),resp.results_errno())
			raise StorageException("while deleting  snapshot %s on volume %s: reason %s error number: %s ",name, self.volume["name"],resp.results_reason(),resp.results_errno())
		NetAppops.logger.debug("snapshot %s deleted",name)
		NetAppops.logger.debug("end")
		return 0
	

			




		
