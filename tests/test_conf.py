from storage_api import conf
from storage_api.utils import merge_two_dicts
from storage_api.apis.common.auth import USER_ROLES

from unittest import mock
import os

import pytest

OAUTH_CONF_KEYS = ['OAUTH_CLIENT_ID', 'OAUTH_SECRET_KEY',
                   'OAUTH_ACCESS_TOKEN_URL', 'OAUTH_AUTHORIZE_URL',
                   'OAUTH_GROUPS_URL',
                   'OAUTH_CALLBACK_URL_RELATIVE']

DEFAULT_OAUTH_CONF = {'SAPI_OAUTH_CLIENT_ID': "dummy",
                      'SAPI_OAUTH_SECRET_KEY': "dummy"}


@mock.patch.dict(os.environ, {})
@pytest.mark.skip(reason="Weirdly fails in python 3.6.4")
def test_read_empty_oauth_env_crashes(temp_app):
    with pytest.raises(KeyError):
        conf.load_oauth_conf(temp_app)


@mock.patch.dict(os.environ, {})
@pytest.mark.skip(reason="Weirdly fails in python 3.6.4")
def test_read_empty_backend_env_crashes(temp_app):
    with pytest.raises(KeyError):
        conf.load_backend_conf(temp_app, backends_module=mock.MagicMock)


@pytest.mark.parametrize('oauth_conf_key', OAUTH_CONF_KEYS)
def test_read_empty_backend_env_values(temp_app, oauth_conf_key):
    sentinel_value = "sentinel_value-123"
    with mock.patch.dict(os.environ,
                         merge_two_dicts(DEFAULT_OAUTH_CONF,
                                         {"SAPI_{}".format(oauth_conf_key):
                                          sentinel_value})):
        conf.load_oauth_conf(temp_app)
        assert temp_app.config[oauth_conf_key] == sentinel_value


@pytest.mark.parametrize('role', USER_ROLES)
def test_set_auth_string(temp_app, role):
    groups = set(["a-group", "another-group", "a-third-group",
                  "a group with spaces"])
    with mock.patch.dict(os.environ,
                         {"SAPI_ROLE_{}_GROUPS".format(role):
                          ",".join(groups)}):
        conf.set_auth_string(temp_app, role)
        assert temp_app.config["{}_GROUPS".format(role)] == groups


@mock.patch.dict(os.environ, {})
def test_set_auth_string_empty_user_env(temp_app):
    conf.set_auth_string(temp_app, 'USER')
    assert temp_app.config['USER_GROUPS'] == set()
    assert temp_app.config['USER_IS_UNAUTHENTICATED']


@mock.patch.dict(os.environ, {'SAPI_ROLE_USER_GROUPS': 'it-db-ims'})
def test_set_auth_string_user_groups_set(temp_app):
    conf.set_auth_string(temp_app, 'USER')
    assert temp_app.config['USER_GROUPS'] == set(['it-db-ims'])
    assert not temp_app.config['USER_IS_UNAUTHENTICATED']
