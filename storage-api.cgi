#!/usr/bin/python3

from wsgiref.handlers import CGIHandler
from storage_api import app

CGIHandler().run(app)
