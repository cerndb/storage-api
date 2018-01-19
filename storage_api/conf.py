# -*- coding: utf-8 -*-
# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from storage_api.utils import pairwise

import os
import csv
import io

# If you're not unicode ready, you're not ready, period.
BACKEND_SEPARATOR = "🦄"
CONFIG_SEPARATOR = "🌈"
BACKENDS_VARIABLE_NAME = "SAPI_BACKENDS"


def conf_to_dict(conf_list):
    # If the length of the configuration is uneven, keys don't match up.
    assert len(conf_list) % 2 == 0
    return dict(pairwise(conf_list))


def load_backend_conf(app, backends_module=None):
    """
    Initialise back-ends into the app app, using the provided module to
    get back-end classes.
    """

    # Placeholder for back-end mappings:
    if 'SUBSYSTEM' not in app.config:
        app.config['SUBSYSTEM'] = {}

    app.logger.info("Loading back-end conf from ${}"
                    .format(BACKENDS_VARIABLE_NAME))
    conf = os.environ[BACKENDS_VARIABLE_NAME]
    backends = conf.split(BACKEND_SEPARATOR)
    for backend_conf in backends:
        conf = backend_conf.split(CONFIG_SEPARATOR)
        endpoint = conf[0]

        # This is the class itself:
        Backend = getattr(backends_module, conf[1])
        conf_dict = conf_to_dict(conf[2:])
        app.logger.debug("Back-end conf dict: {}".format(conf_dict))
        backend = Backend(**conf_dict)
        backend.init_app(app, endpoint=endpoint)


def set_oauth_property(app, key_name, default_value=None):
    """
    Helper: fetch an OAuth property named PROPRETY_NAME from an
    environment variable named SAPI_OAUTH_PROPERTY_NAME into a
    configuration field named OAUTH_PROPERTY_NAME.

    Raises KeyError if the variable is not set and no default value was
    passed.
    """

    internal_key = 'OAUTH_{}'.format(key_name)
    env_key = 'SAPI_{}'.format(internal_key)

    if not default_value and env_key not in os.environ:
        raise KeyError("${} not set!".format(env_key))

    app.config[internal_key] = os.getenv(env_key, default_value)
    app.logger.debug("Set OAuth configuration key {} from {}"
                     .format(internal_key, env_key))


def load_oauth_conf(app):
    """
    Load the OAuth configuration options from the environment and insert
    it into the app's conf dict.
    """
    app.logger.info("Loading OAuth configuration keys...")

    set_oauth_property(app, 'CLIENT_ID')
    set_oauth_property(app, 'SECRET_KEY')
    set_oauth_property(app, 'ACCESS_TOKEN_URL',
                       'https://oauth.web.cern.ch/OAuth/Token')
    set_oauth_property(app, 'AUTHORIZE_URL',
                       'https://oauth.web.cern.ch/OAuth/Authorize')
    set_oauth_property(app, 'GROUPS_URL',
                       'https://oauthresource.web.cern.ch/api/Groups')
    set_oauth_property(app, 'CALLBACK_URL_RELATIVE', '/oauth-done')


def set_auth_string(app, role_name):
    """
    Read and parse the comma-separated list of groups for a given role
    from the environment variable $SAPI_ROLE_X_GROUPS into the app
    configuration key X_GROUPS, as a set.
    """

    role_name = role_name.upper()
    key_name = "{}_GROUPS".format(role_name)
    env_var_name = "SAPI_ROLE_{}".format(key_name)

    group_string = os.getenv(env_var_name, "")

    if not group_string:
        group_data = set()
    else:
        group_data = set(*csv.reader(io.StringIO(group_string),
                                     delimiter=","))
    app.config[key_name] = group_data

    if role_name == 'USER':
        if not group_data:
            app.config['USER_IS_UNAUTHENTICATED'] = True
        else:
            app.config['USER_IS_UNAUTHENTICATED'] = False
