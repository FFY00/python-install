#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='python-install',
    version='0.0.1',
    project_urls={'homepage': 'https://github.com/FFY00/python-install'},
    author='Filipe Laíns',
    author_email='lains@archlinux.org',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3'
    ],
    packages=[
        'install',
        'install._vendor',
        'install._vendor.installer.src.installer',
        'install._vendor.installer.src.installer._compat',
        'install._vendor.installer.src.installer._scripts',
    ],
    extras_require={
        'dependency-checking': [
            'packaging',
            'importlib-metadata; python_version < "3.8"',
        ],
    }
)
