# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from storage_api import conf, apis

from functools import wraps
from typing import Any # noqa

from flask import session, current_app, url_for
import flask
from flask_oauthlib.client import OAuth

USER_ROLES = ["USER", "ADMIN", "UBER_ADMIN"]
USER_ROLE = 'USER_ROLE'
ADMIN_ROLE = 'ADMIN_ROLE'
UBER_ADMIN_ROLE = 'UBER_ADMIN_ROLE'


def setup_roles_from_env(app):
    """
    Configure an application's roles from the environment.
    """

    app.logger.info("Loading authorisation config")
    [conf.set_auth_string(app, role) for role in USER_ROLES]


def setup_oauth(app, login_endpoint, logout_endpoint):
    """
    Setup OAuth2 aunhentication flow for the app with logins initiated by
    going to login_endpoint, and logouts done in logout_endpoint.

    Must be called after the neccessary configuration options have been
    loaded into app.config.
    """

    oauth = OAuth(app)
    callback_url_relative = app.config['OAUTH_CALLBACK_URL_RELATIVE']
    groups_url = app.config['OAUTH_GROUPS_URL']

    cern = oauth.remote_app(
        'cern',
        consumer_key=app.config['OAUTH_CLIENT_ID'],
        consumer_secret=app.config['OAUTH_SECRET_KEY'],
        request_token_url=None,
        access_token_method='POST',
        access_token_url=app.config['OAUTH_ACCESS_TOKEN_URL'],
        authorize_url=app.config['OAUTH_AUTHORIZE_URL'],
    )

    @app.route(login_endpoint)
    def login():
        if app.debug:
            app.logger.warning("Failed login, but authenticating anyway as"
                               " we are in dev mode")
            flask.session['user'] = {}
            flask.session['user']['roles'] = [USER_ROLE,
                                              ADMIN_ROLE,
                                              UBER_ADMIN_ROLE]
            return flask.redirect('/')

        return cern.authorize(callback=url_for('authorized', _external=True))

    @app.route(callback_url_relative)
    def authorized():   # pragma: no cover
        resp = cern.authorized_response()
        if resp is None or resp.get('access_token') is None:
            return 'Access denied: reason=%s error=%s resp=%s' % (
                flask.request.args['error'],
                flask.request.args['error_description'],
                resp
            )
        flask.session['cern_token'] = (resp['access_token'], '')
        app.logger.info("Got authentication call-back from OAuth."
                        " Proceeding to fetch groups...")

        response = cern.get(groups_url).data
        user_groups = set(response['groups'])
        flask.session['user'] = {}
        session_roles = []
        app.logger.debug("OAuth reported the following groups: {}"
                         .format(", ".join(['"{}"'
                                            .format(g) for g in user_groups])))
        if not app.config['USER_GROUPS']:
            app.logger.info("No user groups configured, setting role USER")
            session_roles.append(USER_ROLE)
        for role in USER_ROLES:
            overlap = user_groups.intersection(app.config['{}_GROUPS'
                                                          .format(role)])
            if overlap:
                app.logger.info("User was in {} role groups {}, granting role"
                                .format(role, ", ".join(overlap)))
                session_roles.append(getattr(apis.common, '{}_ROLE'
                                             .format(role)))
            else:
                app.logger.info("User was not in any {} role groups, denying"
                                .format(role))
        app.logger.info("Setting user roles: {}"
                        .format(", ".join(session_roles)))
        flask.session['user']['roles'] = session_roles
        return flask.redirect('/')

    @app.route(logout_endpoint)
    def logout():   # pragma: no cover
        app.logger.info("Current session data: {}".format(str(flask.session)))
        flask.session.pop('cern_token', None)
        flask.session.pop('user', None)
        return flask.redirect('/')

    @cern.tokengetter
    def get_cern_oauth_token():
        return flask.session.get('cern_token')


def in_role(api, group_name):
    """
    Decorator: call flask.abort(403) if user is not in the specified
    group, or if the session is unauthenticated.

    Args:
        api (flask_restplus.Api): The API to signal errors to etc
        group_name (str): A group name to check for membership in

    Example::

        @in_group(api, group_name='it-db-storage')
        def get(self):
            pass

    """

    def group_decorator(func):
        @wraps(func)
        @api.response(403, description=("Current user is not logged in or not"
                                        " a member of the role '{}'")
                      .format(group_name), model=None)
        @api.doc(security=[{'sso': ['read', 'write']}])
        def group_wrapper(*args, **kwargs):
            user = session.get('user', None)
            if not user:
                current_app.logger.error("User not authenticated at all!")
                if current_app.config['USER_IS_UNAUTHENTICATED'] and \
                   group_name == USER_ROLE:
                    current_app.logger.info("Setting user role...")
                    user = {}
                    user['roles'] = set([USER_ROLE])
                    session.user = user
                else:
                    api.abort(403, "The current user is not logged in!")

            current_app.logger.info("Testing if user is in group {}"
                                    .format(group_name))

            if group_name in user.get('roles', []):
                current_app.logger.info("The user had role {}!"
                                        .format(group_name))
                return func(*args, **kwargs)
            else:
                current_app.logger.error("Logged-in user did not have role {}"
                                         .format(group_name))
                current_app.logger.debug("User had roles {}"
                                         .format(", "
                                                 .join(user.get('roles', []))))

                api.abort(403, "The user does not have the role {}"
                          .format(group_name))
        return group_wrapper
    return group_decorator
