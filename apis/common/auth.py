# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from functools import wraps

from flask import session, current_app


def in_group(api, group_name):
    """
    Decorator: call flask.abort(403) if user is not in the specified
    group, or if the session is unauthenticated.

    Usage:
    ```
    @in_group(api, group_name='it-db-storage')
    def get(self):
      pass
    ```
    """

    def group_decorator(func):
        @wraps(func)
        @api.response(403, description=("Current user is not logged in or not"
                                        " a member of the group '{}'")
                      .format(group_name), model=None)
        def group_wrapper(*args, **kwargs):
            user = session.get('user', None)
            if not user:
                current_app.logger.error("User not authenticated at all")
                api.abort(403, "The current user is not logged in!")

            current_app.logger.info("Testing if user is in group {}"
                                    .format(group_name))

            if group_name in user.get('group', []):
                return func(*args, **kwargs)
            else:
                current_app.logger.error("Logged-in user is not in group {}"
                                         .format(group_name))

                api.abort(403, "The user is not in the group {}"
                          .format(group_name))
        return group_wrapper
    return group_decorator
