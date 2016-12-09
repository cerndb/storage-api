# -*- coding: utf-8 -*-

# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.


import flask


def in_group(group_name, session=flask.session, group_key='group'):
    """
    Decorator: call flask.abort(403) if user is not in the specified
    group, or if the session is unauthenticated.

    Usage:
    ```
    @in_group(group_name='it-db-storage')
    def get(self):
      pass
    ```
    """

    def group_decorator(func):
        def group_wrapper(*args, **kwargs):
            try:
                if session['user'][group_key]:
                    return func(*args, **kwargs)
                else:
                    raise KeyError
            except KeyError:
                flask.abort(403)
        return group_wrapper
    return group_decorator
