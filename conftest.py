# content of conftest.py
import os

import pytest
from hypothesis import settings, Verbosity

settings.register_profile("ci", settings(max_examples=10))
settings.register_profile("dev", settings(max_examples=10))
settings.register_profile("debug", settings(max_examples=10, verbosity=Verbosity.verbose))
settings.load_profile(os.getenv(u'HYPOTHESIS_PROFILE', 'default'))


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true",
                     help="run slow tests")


def pytest_runtest_setup(item):
    if 'slow' in item.keywords and not item.config.getvalue("runslow"):
        pytest.skip("need --runslow option to run")
