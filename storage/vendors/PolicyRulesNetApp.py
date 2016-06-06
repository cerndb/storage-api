#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging
import sys
from storage.vendors.BasicStorage import BasicStorage
from storage.vendors.StorageException import StorageException
from storage.vendors.NetAppops import NetAppops
sys.path.append("/opt/netapp-manageability-sdk-5.4P1/lib/python/NetApp")  # noqa
from NaServer import *                                                    # noqa


class PolicyRulesNetApp(NetAppops, BasicStorage):
    '''This class handles the access to a given file system, it also handles the creation/destruction of policies together with individual rules.'''
    def __init__(self, serverpath):
        if __name__ == '__main__':
            PolicyRulesNetApp.logger = logging.getLogger('storage-api-console')
        else:
            PolicyRulesNetApp.logger = logging.getLogger('storage-api')
        PolicyRulesNetApp.logger.debug("begin")
        NetAppops.__init__(self, serverpath)
        PolicyRulesNetApp.logger.debug("end")

    @staticmethod
    def NewVolume(serverpath, vserver):
        '''While operating with Rules and Policies, a volume is required.'''
        comodin = PolicyRulesNetApp(serverpath)
        comodin.volume['vserver'] = vserver
        return comodin

    @staticmethod
    def ExistingVolume(serverpath):
        '''While operating with Rules and Policies, a volume is required.'''
        comodin = PolicyRulesNetApp(serverpath)
        comodin.GetInfoPath(0)
        return comodin

    def PolicyCreate(self, policy):
        ''' Create a new policy'''
        PolicyRulesNetApp.logger.debug("begin")
        policyxml = NaElement("export-policy-create")
        policyxml.child_add_string("policy-name", policy)
        policyxml.child_add_string("return-record", 'true')

        if self.server_zapi is None and 'vserver' in self.volume:
            self.server_zapi = super(PolicyRulesNetApp, self).CreateServer(self.clustertoconnect[0],
                                                                           self.volume['vserver'])
        else:
            PolicyRulesNetApp.logger.debug('a vserver is required')
            raise StorageException('a vserver is required')

        PolicyRulesNetApp.logger.debug("query looks like: %s", policyxml.sprintf())

        resp = self.server_zapi.invoke_elem(policyxml)
        if (resp and resp.results_errno() != 0):
            PolicyRulesNetApp.logger.error("some error while trying to create policy %s" % resp.results_reason())
            PolicyRulesNetApp.logger.debug("end")
            raise StorageException("Error while creating policy: %s" % resp.results_reason())

        PolicyRulesNetApp.logger.debug("end")
        return 0

    def CreateRuleREST(self, ip):
        '''Add a new rule to an existing policy. '''
        PolicyRulesNetApp.logger.debug("begin")
        if 'policy' in self.volume.keys():
            return self.CreateRule(self.volume['policy'], ip)
        else:
            raise StorageException(
                "volume dictionary has not been initialised. This method needs to be called from an existing volume.")

    def CreateRule(self, policy, ip):
        '''Create a rule if it's not existent.'''
        match = self.GetRule(policy, ip)
        if match is None:
            rule = NaElement("export-rule-create")
            rule.child_add_string("policy-name", policy)
            rule.child_add_string("client-match", ip)
            # always 1 to put the new rule on top
            rule.child_add_string("rule-index", "1")
            rorule = NaElement("ro-rule")
            rule.child_add(rorule)
            rorule.child_add_string("security-flavor", "sys")
            rwrule = NaElement("rw-rule")
            rule.child_add(rwrule)
            rwrule.child_add_string("security-flavor", "sys")
            rule.child_add_string("anonymous-user-id", "0")
            protocol = NaElement("protocol")
            rule.child_add(protocol)
            protocol.child_add_string("access-protocol", "nfs")
            suser = NaElement("super-user-security")
            rule.child_add(suser)
            suser.child_add_string("security-flavor", "sys")

            if self.server_zapi is None:
                super(PolicyRulesNetApp, self).CreateServer(self.clustertoconnect[0], self.volume['vserver'])
            PolicyRulesNetApp.logger.debug("query looks like: %s", rule.sprintf())

            resp = self.server_zapi.invoke_elem(rule)

            if (resp and resp.results_errno() != 0):
                NetAppops.logger.debug("cant create the rule: reason %s error number: %s ", resp.results_reason(),
                                       resp.results_errno())
                return None
            else:
                NetAppops.logger.debug("Rule has been created!")
                return 0
        else:
            NetAppops.logger.debug("Rule was already there!")
            return 0

    def GetRule(self, policy, ip):
        '''Check if a given IP is part of a policy's rules.'''
        PolicyRulesNetApp.logger.debug("begin")
        allrules = self.GetRuleAll(policy)
        if allrules is None:
            return None
        else:
            if ip in allrules.values():
                for key in allrules:
                    if allrules[key] == ip:
                        PolicyRulesNetApp.logger.debug("rule index is: %s for ip: %s", key, ip)
                        PolicyRulesNetApp.logger.debug("end")
                        return key
            else:
                PolicyRulesNetApp.logger.debug("rule %s not found", ip)
                PolicyRulesNetApp.logger.debug("end")
                return None

    def GetRuleAllREST(self):
        '''Get all rules linked to a tuple: controller + mount point'''
        PolicyRulesNetApp.logger.debug("begin")
        if 'policy' in self.volume.keys():
            return self.GetRuleAll(self.volume['policy'])
        else:
            raise StorageException(
                "volume dictionary has not been initialised. This method needs to be called from an existing volume.")

    def GetRuleAll(self, policy):
         '''List all rules on a given policy.'''
        PolicyRulesNetApp.logger.debug("begin")
        tag = "more"
        allrules = {}
        first = 0
        while tag:
            iter = NaElement("export-rule-get-iter")
            iter.child_add_string("max-records", 40)
            if first > 0:
                iter.child_add_string("tag", tag)
            xi = NaElement("desired-attributes")
            iter.child_add(xi)
            xi1 = NaElement("export-rule-info")
            xi.child_add(xi1)
            xi1.child_add_string("client-match", "")
            xi1.child_add_string("rule-index", "")
            query = NaElement("query")
            iter.child_add(query)
            param = NaElement("export-rule-info")
            query.child_add(param)
            param.child_add_string("policy-name", policy)

            param.child_add_string("vserver-name", self.volume['vserver'])
            PolicyRulesNetApp.logger.debug("query looks like: %s", iter.sprintf())

            if self.server_zapi is None:
                super(PolicyRulesNetApp, self).CreateServer(self.clustertoconnect[0], self.volume['vserver'])

            resp = self.server_zapi.invoke_elem(iter)
            if (resp and resp.results_errno() != 0):
                NetAppops.logger.error("no rules retrieved : reason %s error number: %s ", resp.results_reason(),
                                       resp.results_errno())
                PolicyRulesNetApp.logger.debug("end")
                return None
            else:
                list = resp.child_get("attributes-list")
                if list:
                    attlist = list.children_get()
                    for elem in attlist:
                        cm = elem.child_get_string("client-match")
                        ri = elem.child_get_string("rule-index")
                        PolicyRulesNetApp.logger.debug("Adding index: %s and maching rule: %s", ri, cm)
                        allrules[ri] = cm
            tag = resp.child_get_string("next-tag")
            first += 1
        PolicyRulesNetApp.logger.debug("end")
        return allrules

    def DeleteRuleREST(self, ip):
        ''' Deletes a certain indexed rule in a policy and re-orders remaining rules.'''
        if 'policy' in self.volume.keys():
            return self.DeleteRule(self.volume['policy'], ip)
        else:
            raise StorageException(
                "volume dictionary has not been initialised. This method needs to be called from an existing volume.")

    def DeleteRule(self, policy, ip):
        ''' Deletes a certain indexed rule in a policy and re-orders remaining rules.'''
        PolicyRulesNetApp.logger.debug("begin")
        rules = {}
        index = self.GetRule(policy, ip)
        if not index:
            PolicyRulesNetApp.logger.debug("Rule: %s in policy: %s doesnt exist.", ip, policy)
            return 0

        api = NaElement("export-rule-destroy")
        api.child_add_string("policy-name", policy)
        api.child_add_string("rule-index", index)

        if self.server_zapi is None:
            super(PolicyRulesNetApp, self).CreateServer(self.clustertoconnect[0], self.volume['vserver'])

        resp = self.server_zapi.invoke_elem(api)
        if (resp and resp.results_errno() != 0):
            PolicyRulesNetApp.logger.debug("cant delete the rule: reason %s error number: %s ", resp.results_reason(),
                                           resp.results_errno())
            return None
        else:
            PolicyRulesNetApp.logger.debug("Rule %s in policy %s has been deleted!", ip, policy)

        rules = self.GetRuleAll(policy)
        if rules:
            sortedkeys = sorted(list(rules))
            for i in range(0, len(sortedkeys), 1):
                if (sortedkeys[i] == (i + 1)):
                    continue
                in2 = NaElement("export-rule-set-index")
                in2.child_add_string("policy-name", policy)
                in2.child_add_string("rule-index", sortedkeys[i])
                in2.child_add_string("new-rule-index", i + 1)
                PolicyRulesNetApp.logger.debug("Old index: %s New index: %s", sortedkeys[i - 1], i + 1)
                resp2 = self.server_zapi.invoke_elem(in2)
                if (resp2 and resp2.results_errno() != 0):
                    PolicyRulesNetApp.logger.debug("cant re-index the rule: reason %s error number: %s ",
                                                   resp2.results_reason(), resp2.results_errno())
                    return None
        else:
            NetAppops.logger.debug("No more rules available")

        NetAppops.logger.debug("Rule %s was deleted in policy: %s", ip, policy)
        PolicyRulesNetApp.logger.debug("end")
        return 0

    def PolicyDelete(self, policy):
        '''Delete a policy. No volume should be using it!.'''
        PolicyRulesNetApp.logger.debug("begin")

        oldpol = NaElement("export-policy-destroy")
        oldpol.child_add_string("policy-name", policy)

        if self.server_zapi is None:
            super(PolicyRulesNetApp, self).CreateServer(self.clustertoconnect[0], self.volume['vserver'])

        resp = self.server_zapi.invoke_elem(oldpol)
        if (resp and resp.results_errno() != 0):
            PolicyRulesNetApp.logger.debug("cant delete policy %s: reason %s error number: %s ", policy,
                                           resp.results_reason(), resp.results_errno())
            return None

        PolicyRulesNetApp.logger.debug("policy %s was deleted.", policy)

        PolicyRulesNetApp.logger.debug("End")
        return 0
