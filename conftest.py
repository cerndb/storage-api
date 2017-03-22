# content of conftest.py
import os
import base64

import pytest
from hypothesis import settings, Verbosity

import betamax
from betamax_serializers import pretty_json

betamax.Betamax.register_serializer(pretty_json.PrettyJSONSerializer)

ontap_username = os.environ.get('ONTAP_USERNAME', 'user-placeholder')
ontap_password = os.environ.get('ONTAP_PASSWORD', 'password-placeholder')

settings.register_profile("ci", settings(max_examples=10))
settings.register_profile("exhaustive", settings(max_examples=400))
settings.register_profile("dev", settings(max_examples=10))
settings.register_profile("debug", settings(max_examples=10, verbosity=Verbosity.verbose))
settings.load_profile(os.getenv(u'HYPOTHESIS_PROFILE', 'dev'))


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true",
                     help="run slow tests")
    parser.addoption("--betamax-record-mode", action="store", default="never",
                     help="Use betamax recording option (once, new_episodes, never)")


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
    config.define_cassette_placeholder('<ONTAP-AUTH>',
                                       base64.b64encode(
                                           ('{0}:{1}'
                                            .format(ontap_username,
                                                    ontap_password)).encode('utf-8'))
                                       .decode('utf-8'))
