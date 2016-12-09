#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "LICENSE".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

"""
Storage REST API server setup file
"""

from setuptools import setup, find_packages
import apis

setup(name='storage-api',
      version=apis.__version__,
      description='DB Storage REST API',
      author='CERN',
      author_email='rgaspar@cern.ch',
      license='GPLv3',
      maintainer='Ruben Gaspar',
      maintainer_email='rgaspar@cern.ch',
      url='https://github.com/cerndb/storage-api',
      packages=find_packages(),
      scripts=['app.py'],
      test_suite="",
      requires=[
          'ConfigParser',
          'flask_restplus',
          'flask',
          'flask_sso',
      ])
