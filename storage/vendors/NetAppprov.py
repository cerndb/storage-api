#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.


import sys
import logging
from storage.config import CONFIG
from storage.vendors.BasicStorage import BasicStorage
from storage.vendors.NetAppops import NetAppops
from storage.vendors.StorageException import StorageException
from storage.vendors.PolicyRulesNetApp import PolicyRulesNetApp

sys.path.append("/opt/netapp-manageability-sdk-5.4P1/lib/python/NetApp")
from NaServer import *


class NetAppprov(NetAppops, BasicStorage):
    def __init__(self, clustername, volname, initial_size, final_size, increment, vserver, firewall_name, junction_path,
                 type, firewall_ip=0, snaps=0, business=0):
        # At this point we dont know if the volume exists, create a potentially fake name
        if __name__ == '__main__':
            NetAppprov.logger = logging.getLogger('storage-api-console')
        else:
            NetAppprov.logger = logging.getLogger('storage-api')

        serverpath = clustername + str(222) + ":" + junction_path
        NetAppops.__init__(self, serverpath)
        NetAppprov.logger.debug("Begin")
        # should we use a subset or all possible aggregates
        self.volname = volname.lower()
        assert re.search('^[\-_\w]+$', self.volname), "volume name contains strange characters"
        self.initial_size = initial_size
        self.final_size = final_size
        self.increment = increment
        self.firewall_ip = firewall_ip
        self.firewall_name = firewall_name
        self.junction_path = junction_path
        self.business = business
        self.vserver = vserver
        self.volume['vserver'] = vserver
        self.clustername = clustername

        # Apriori we dont want snapshots, snaps equal 0
        NetAppprov.logger.debug("snaps is: %s " % str(snaps))
        self.snaps = snaps
        # type can be: hybrid-aggr, hdd-aggr, ssd-aggr
        self.type = type
        # let's try to see if there is an spefic
        if business == 0:
            self.business = clustername
            NetAppprov.logger.debug("business is: %s", business)
        self.admin_server = None
        self.admin_vserver = None
        NetAppprov.logger.debug("End")

    @staticmethod
    def ExistingVol(serverpath):
        comodin = NetAppops(serverpath)
        try:
            comodin.GetInfoPath()
        except:
            return None
        if 'vserver' in comodin.volume.keys():
            return NetAppprov(comodin.clustertoconnect[0], comodin.volume['name'], 1, 1, 1, comodin.volume['vserver'],
                              comodin.volume['policy'], comodin.volume['junction-path'], 'hybrid-aggr')
        else:
            return None

    def __FindAggregate(self):
        '''Retrieve the aggregate that has available size'''
        NetAppprov.logger.debug("Begin")
        candidate = {}
        if CONFIG[self.business][self.vserver]["nodes"]:
            for key in CONFIG[self.business][self.vserver]["nodes"]:
                if CONFIG[self.business][self.vserver]["nodes"][key][self.type]:
                    dict_aggrpernode = self.__AggregateFreeSize(key)

                    for key2 in CONFIG[self.business][self.vserver]["nodes"][key][self.type]:
                        comodin = key + ':' + key2
                        if comodin in dict_aggrpernode:
                            candidate[comodin] = dict_aggrpernode[comodin]
                            NetAppprov.logger.debug("%s size %s beeing added to candidate", comodin,
                                                    str(dict_aggrpernode[comodin]))
        else:
            NetAppprov.logger.debug("End")
            return None
        # sorted
        sorted_candidate = sorted(candidate, key=candidate.get, reverse=True)
        NetAppprov.logger.debug("possible aggregates: %s", sorted_candidate)
        NetAppprov.logger.debug("chosen one: %s", sorted_candidate[0])
        NetAppprov.logger.debug("End")
        return sorted_candidate[0]

    def __AggregateFreeSize(self, node):
        ''' It gets back all aggregates belonging to a node (controller) and their available size. Value in bytes. '''
        NetAppprov.logger.debug("Begin")

        api1 = NaElement("aggr-get-iter")
        # We expect just one element
        api1.child_add_string("max-records", 20)
        query = NaElement("query")
        aggr_parent = NaElement("aggr-attributes")
        query.child_add(aggr_parent)
        towhom = NaElement("nodes")
        aggr_parent.child_add(towhom)
        towhom.child_add_string("node-name", node)
        api1.child_add(query)
        desiredAttrs = NaElement("desired-attributes")
        desiredSpace = NaElement("aggr-space-attributes")
        desiredAttrs.child_add(desiredSpace)
        api1.child_add(desiredAttrs)

        NetAppprov.logger.debug("query looks like: %s", api1.sprintf())

        # if self.admin_server is None:
        #
        self.admin_server = super(NetAppprov, self).CreateServer(self.clustertoconnect[0])
        resp = self.admin_server.invoke_elem(api1)

        if isinstance(resp, NaElement) and resp.results_errno() != 0:
            NetAppprov.logger.error("query failed: reason %s error number: %s ", resp.results_reason(),
                                    resp.results_errno())
            raise StorageException("query failed: reason %s error number: %s ", resp.results_reason(),
                                   resp.results_errno())

        if isinstance(resp, NaElement) and resp.child_get_int("num-records") == 0:
            NetAppprov.logger.error("query returned 0 records.")
            raise StorageException("query returned 0 records.")

        aggrList = resp.child_get("attributes-list").children_get()
        result = {}
        for aggrInfo in aggrList:
            aggr_name = aggrInfo.child_get_string("aggregate-name")
            aggrSizeAttrs = aggrInfo.child_get("aggr-space-attributes")
            if aggrSizeAttrs:
                aggrfreesize = aggrSizeAttrs.child_get_string("size-available")
            result[node + ':' + aggr_name] = aggrfreesize

        NetAppprov.logger.debug("aggregate information for node: %s is %s", node, result)

        NetAppprov.logger.debug("End")
        return result

    def CreateVolume(self):
        '''Basic volume creation'''
        NetAppprov.logger.debug("begin")
        try:
            volume = self.GetInfoPath()
        except Exception as ex:
            volume = None
            NetAppprov.logger.debug("Volume doesnt exist %s" % str(ex))
        if volume is not None:
            NetAppprov.logger.debug("volume with %s junction-path exists with name: %s", self.junction_path,
                                    volume['name'])
            NetAppprov.logger.debug("end")
            return 0
        else:
            # let's create the volume
            comodin = self.__FindAggregate()
            if comodin is None or ':' not in comodin:
                NetAppprov.logger.error("proper aggregate couldnt retrieved")
                raise StorageException("proper aggregate couldnt retrieved")
            (node, aggregate) = comodin.split(':', 2)
            api1 = NaElement("volume-create")
            api1.child_add_string("volume", self.volname)
            api1.child_add_string("containing-aggr-name", aggregate)
            api1.child_add_string("size", str(self.initial_size) + 'g')
            api1.child_add_string("junction-path", self.junction_path)
            api1.child_add_string("snapshot-policy", "none")
            if self.snaps:
                api1.child_add_string("percentage-snapshot-reserve", "20")
            else:
                api1.child_add_string("percentage-snapshot-reserve", "0")

            if self.admin_vserver is None:
                self.admin_vserver = super(NetAppprov, self).CreateServer(self.business, self.vserver)

            if self.firewall_name:
                serverpath = self.clustername + str(222) + ":" + self.junction_path
                policies = PolicyRulesNetApp.NewVolume(serverpath, self.vserver)
                chpol = NaElement("export-policy-get")
                chpol.child_add_string("policy-name", self.firewall_name)
                resp = self.admin_vserver.invoke_elem(chpol)
                if (resp and resp.results_errno() != 0):
                    # policy needs to be created
                    try:
                        resp = policies.PolicyCreate(self.firewall_name)
                    except:
                        raise StorageException("Error while creating policy")
                    else:
                        if (resp == 0):
                            NetAppprov.logger.debug("policy %s has been created.", self.firewall_name)

                api1.child_add_string("export-policy", self.firewall_name)

                if self.firewall_ip:
                    resp = policies.CreateRule(self.firewall_name, self.firewall_ip)
                    if (resp == 0):
                        NetAppprov.logger.debug("rule %s has been added.", self.firewall_ip)

            NetAppprov.logger.debug("query looks like: %s", api1.sprintf())

            resp = self.admin_vserver.invoke_elem(api1)
            if (resp and resp.results_errno() != 0):
                NetAppprov.logger.error("some error while trying to create volume %s", resp.results_reason())
                NetAppprov.logger.debug("end")
                raise StorageException("Error while creating volume: %s", resp.results_reason())

        # volume created!

        if self.snaps:
            resp = self.SetSnapAutoDeletion("snap_reserve", 10, "oldest_first", "scheduled")
            if resp == 0:
                NetAppprov.logger.debug("snapautodeletion set for volume: %s", self.volname)
            else:
                NetAppprov.logger.debug("snapautodeletion failed for volume: %s", self.volname)
        # Autosize
        if int(self.final_size) > 0 and int(self.increment) > 0:
            resp = self.SetAutoSize(self.final_size, self.increment)
            if resp == 0:
                NetAppprov.logger.debug("autosize set for volume: %s", self.volname)
            else:
                NetAppprov.logger.debug("autosize failed for volume: %s", self.volname)

        NetAppprov.logger.debug("volume has been created!!")
        NetAppprov.logger.debug("end")
        return 0

    def SetAutoSize(self, maxsize, increment):
        '''All values provided on GB'''
        NetAppprov.logger.debug("begin")
        if self.admin_vserver is None:
            self.admin_vserver = super(NetAppprov, self).CreateServer(self.business, self.vserver)

        if increment == 0:
            resp = self.admin_vserver.invoke("volume-autosize-set", "volume", self.volname, "maximum-size",
                                             str(maxsize) + 'g', "is-enabled", "true")
        else:
            resp = self.admin_vserver.invoke("volume-autosize-set", "volume", self.volname, "increment-size",
                                             str(increment) + 'g', "maximum-size", str(maxsize) + 'g', "is-enabled",
                                             "true")

        if isinstance(resp, NaElement) and resp.results_errno() != 0:
            NetAppprov.logger.error("query failed: reason %s error number: %s ", resp.results_reason(),
                                    resp.results_errno())
            return None

        NetAppprov.logger.debug("autosize for volume: %s set to a maximum size of %s GB and increment of %s GB.",
                                self.volname, maxsize, increment)
        NetAppprov.logger.debug("end")
        return 0

    def RestrictVolume(self):
        ''' In reality volume is restricted. No NFS access.'''
        NetAppprov.logger.debug("begin")
        in1 = NaElement("volume-unmount")
        if self.volname:
            in1.child_add_string("volume-name", self.volname)
        else:
            raise StorageException("internal structure hasnt been initialized.")
        if self.admin_vserver is None:
            self.admin_vserver = super(NetAppprov, self).CreateServer(self.business, self.vserver)
        resp = self.admin_vserver.invoke_elem(in1)
        if (resp and resp.results_errno() != 0):
            NetAppprov.logger.error("some error while trying to unmount volume %s", resp.results_reason())
            NetAppprov.logger.debug("end")
            raise StorageException("Error while unmount volume: %s", resp.results_reason())

        api = NaElement('volume-restrict')
        api.child_add_string('name', self.volname)
        self.admin_vserver.invoke_elem(api)
        if (resp and resp.results_errno() != 0):
            NetAppprov.logger.error("some error while trying to restrict volume %s", resp.results_reason())
            NetAppprov.logger.debug("end")
            raise StorageException("Error while restrict volume: %s", resp.results_reason())

        NetAppprov.logger.debug("Volume %s has been restricted." % self.volname)
        NetAppprov.logger.debug("end")
        return 0

    def DeleteVolume(self):
        '''Deletes a volume permanently!'''
        NetAppprov.logger.debug("begin")
        in1 = NaElement("volume-unmount")
        if self.volname:
            in1.child_add_string("volume-name", self.volname)
        else:
            raise StorageException("internal structure hasnt been initialized.")
        if self.admin_vserver is None:
            self.admin_vserver = super(NetAppprov, self).CreateServer(self.business, self.vserver)
        resp = self.admin_vserver.invoke_elem(in1)
        if (resp and resp.results_errno() != 0):
            NetAppprov.logger.error("some error while trying to unmount volume %s", resp.results_reason())
            NetAppprov.logger.debug("end")
            raise StorageException("Error while unmount volume: %s", resp.results_reason())
        in2 = NaElement("volume-offline")
        in2.child_add_string("name", self.volname)
        resp = self.admin_vserver.invoke_elem(in2)
        if (resp and resp.results_errno() != 0):
            NetAppprov.logger.error("some error while trying to offline volume %s", resp.results_reason())
            NetAppprov.logger.debug("end")
            raise StorageException("Error while offline volume: %s", resp.results_reason())
        in3 = NaElement("volume-destroy")
        in3.child_add_string("name", self.volname)
        resp = self.admin_vserver.invoke_elem(in3)
        if (resp and resp.results_errno() != 0):
            NetAppprov.logger.error("some error while trying to destroy volume %s", resp.results_reason())
            NetAppprov.logger.debug("end")
            raise StorageException("Error while destroy volume: %s", resp.results_reason())

        NetAppprov.logger.debug("Volume %s has been deleted." % self.volname)
        NetAppprov.logger.debug("end")
        return 0

    def SetSnapAutoDeletion(self, trigger, space, order, delpolicy):
        '''Setting Snap autodeletion.'''
        NetAppprov.logger.debug("begin")
        snapmod = NaElement("volume-modify-iter")
        query = NaElement("query")
        snapmod.child_add(query)
        att = NaElement("attributes")
        snapmod.child_add(att)
        volattr = NaElement("volume-attributes")
        att.child_add(volattr)
        snattr = NaElement("volume-snapshot-autodelete-attributes")
        snamgmt = NaElement("volume-space-attributes")
        volattr.child_add(snattr)
        volattr.child_add(snamgmt)
        snattr.child_add_string("trigger", trigger)
        snattr.child_add_string("target-free-space", space)
        snattr.child_add_string("delete-order", order)
        snattr.child_add_string("defer-delete", delpolicy)
        snattr.child_add_string("is-autodelete-enabled", "true")
        snamgmt.child_add_string("space-mgmt-option-try-first", "snap_delete")
        volattr2 = NaElement("volume-attributes")
        query.child_add(volattr2)
        volid = NaElement("volume-id-attributes")
        volattr2.child_add(volid)
        volid.child_add_string("name", self.volname)
        volid.child_add_string("owning-vserver-name", self.vserver)

        if self.admin_vserver is None:
            self.admin_vserver = super(NetAppprov, self).CreateServer(self.business, self.vserver)

        NetAppprov.logger.debug("query looks like: %s", snapmod.sprintf())

        resp = self.admin_vserver.invoke_elem(snapmod)
        if isinstance(resp, NaElement) and resp.results_errno() != 0:
            NetAppprov.logger.debug("failed to set snap autodeletion configuration with error: %s error number: %s ",
                                    resp.results_reason(), resp.results_errno())
            return None

        NetAppprov.logger.debug("snap autodeletion configuration set for %s", self.volname)
        NetAppprov.logger.debug("end")
        return 0
