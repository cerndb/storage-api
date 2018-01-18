# content of conftest.py
# -*- coding: utf-8 -*-

from storage_api import extensions

import os
import base64
import logging

import pytest
from hypothesis import settings, Verbosity

import betamax
from betamax_serializers import pretty_json
from unittest import mock

log = logging.getLogger(__name__)

betamax.Betamax.register_serializer(pretty_json.PrettyJSONSerializer)

ontap_username = os.environ.get('ONTAP_USERNAME', 'user-placeholder')
ontap_password = os.environ.get('ONTAP_PASSWORD', 'password-placeholder')
ontap_hostname = os.environ.get('ONTAP_HOST', 'host-placeholder')
ontap_vserver = os.environ.get('ONTAP_VSERVER', 'vserver-placeholder')

settings.register_profile("ci", settings(max_examples=10))
settings.register_profile("exhaustive", settings(max_examples=400))
settings.register_profile("dev", settings(max_examples=10))
settings.register_profile("debug", settings(max_examples=10,
                                            verbosity=Verbosity.verbose))
settings.load_profile(os.getenv(u'HYPOTHESIS_PROFILE', 'dev'))


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true",
                     help="run slow tests")
    parser.addoption("--betamax-record-mode", action="store", default="never",
                     help=("Use betamax recording option "
                           "(once, new_episodes, never)"))


def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getvalue("runslow"):
        pytest.skip("need --runslow option to run")


with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'
    config.default_cassette_options['serialize_with'] = 'prettyjson'
    config.default_cassette_options['match_requests_on'] = ['uri', 'method']
    # Replace the base64-encoded username:password string in the
    # basicauth headers with a placeholder to avoid exposing cleartext
    # passwords in checked-in content.
    config.define_cassette_placeholder(
        '<ONTAP-AUTH>',
        base64.b64encode(
            ('{0}:{1}'.format(ontap_username,
                              ontap_password)).encode('utf-8'))
        .decode('utf-8'))

    config.define_cassette_placeholder('<ONTAP-HOST>', ontap_hostname)
    config.define_cassette_placeholder('<ONTAP-VSERVER>', ontap_vserver)


@pytest.fixture(scope="function")
def temp_app(request):
    """
    Fixture to set up a test app.
    """

    with mock.patch.dict(os.environ, {'SAPI_BACKENDS':
                                      ("dummy🌈DummyStorage🦄"
                                       "netapp🌈DummyStorage🦄"
                                       "ceph🌈DummyStorage"),
                                      'SAPI_OAUTH_CLIENT_ID': "dummy",
                                      'SAPI_OAUTH_SECRET_KEY': "dummy"}):
        from storage_api import app

    app.app.testing = True

    yield app.app



@pytest.fixture(scope="function")
def client(temp_app):
    """
    Fixture to set up a Flask test client
    """

    extensions.DummyStorage().init_app(temp_app, endpoint="dummy")
    extensions.DummyStorage().init_app(temp_app, endpoint="netapp")
    extensions.DummyStorage().init_app(temp_app, endpoint="ceph")

    with temp_app.test_client() as client:
        yield client

    log.debug("App teardown initiated: re-initialising dummy backend")
    extensions.DummyStorage().init_app(temp_app, endpoint="dummy")
    extensions.DummyStorage().init_app(temp_app, endpoint="netapp")
    extensions.DummyStorage().init_app(temp_app, endpoint="ceph")
