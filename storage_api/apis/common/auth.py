# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from functools import wraps
from typing import Any # noqa

from flask import session, current_app

USER_ROLE = 'USER_ROLE'
ADMIN_ROLE = 'ADMIN_ROLE'
UBER_ADMIN_ROLE = 'UBER_ADMIN_ROLE'


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
