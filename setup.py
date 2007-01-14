#!/usr/bin/env python
"""Distutils setup file"""

#import ez_setup
#ez_setup.use_setuptools()
from setuptools import setup

# Metadata
PACKAGE_NAME = "WebHaiku"
PACKAGE_VERSION = "0.5"

def get_description():
    # Get our long description from the documentation
    f = file('README.txt')
    lines = []
    for line in f:
        if not line.strip():
            break     # skip to first blank line
    for line in f:
        if line.startswith('.. contents::'):
            break     # read to table of contents
        lines.append(line)
    f.close()
    return ''.join(lines)

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description='A class-oriented, egg-savvy, "ultralite" WSGI framework',
    long_description = get_description(),

    author="Phillip J. Eby",
    author_email="peak@eby-sarna.com",
    license="PSF or ZPL",
    #url="...",
    test_suite = 'web_haiku',
    py_modules = ['web_haiku'],

    install_requires = 'wsgiref>=0.1',


    entry_points = {
        'wsgirun.apps': ['/ = web_haiku:TestContainer']
    }
    
)




































