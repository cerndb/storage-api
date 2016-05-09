#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from flask import Flask, session, request, redirect
from flask_sso import SSO
from flask.ext.restful import Api, Resource
from storage.api.PathREST import PathREST
from storage.api.VolumeREST import VolumeREST
from storage.api.RulesREST import RulesREST
import os
from datetime import datetime

app = Flask(__name__)
app.debug = True
SSO_ATTRIBUTE_MAP = {
	'ADFS_LOGIN': (True, 'username'),
	'ADFS_FULLNAME': (True, 'fullname'),
	'ADFS_PERSONID': (True, 'personid'),
	'ADFS_DEPARTMENT': (True, 'department'),
	'ADFS_EMAIL': (True, 'email'),
	'ADFS_GROUP': (True, 'Group')
}
app.config.setdefault('SSO_ATTRIBUTE_MAP', SSO_ATTRIBUTE_MAP)
app.config.setdefault('SSO_LOGIN_URL', '/login')
ext = SSO(app=app)
app.secret_key = os.urandom(24)

def get_user_session_info(key):
	return session['user'].get(
		key,
		'Key `{0}` not found in user session info'.format(key)
    	)


def get_user_details(fields):
	defs = [
		'<dt>{0}</dt><dd>{1}</dd>'.format(f, get_user_session_info(f))
		for f in fields
    	]
	return '<dl>{0}</dl>'.format(''.join(defs))

@ext.login_handler
def login(user_info):
  session["user"] = user_info
  return redirect('/')

#test code for SSO
@app.route('/')
def index():
	time = datetime.now().time()
	timestr = '{0:02d}:{1:02d}:{2:02d}'.format(time.hour, time.minute, time.second)
	headings = '<h1>Hello, World!</h1><h2>Server time: {0}</h2>'.format(timestr)
	if 'user' in session:
		details = get_user_details([
			'username',
			'fullname',
			'email',
			'department',
			'personid',
			'Group'
			])
		button = (
			'<form action="/logout" method="get">'
			'<input type="submit" value="Log out">'
			'</form>'
			)
	else:
		details = ''
		button = (
			'<form action="/login" method="get">'
			'<input type="submit" value="Log in">'
			'</form>'
			)
	return headings + details + button


api = Api(app)

api.add_resource(PathREST, '/storage/api/v1.0/paths/<string:path>')
api.add_resource(VolumeREST, '/storage/api/v1.0/volumes/<string:volname>')
api.add_resource(RulesREST, '/storage/api/v1.0/exports/<string:path>')

if __name__ == '__main__':
    app.run()