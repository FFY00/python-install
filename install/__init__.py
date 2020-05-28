# SPDX-License-Identifier: MIT

'''
python-install - A simple, correct PEP427 wheel installer
'''
__version__ = '0.0.1'

import compileall
import logging
import pickle
import os
import re
import site
import shutil
import sys
import sysconfig
import zipfile

if sys.version_info >= (3, 5) or (sys.version_info < (3,) and sys.version_info >= (2, 7)):
    from typing import List, Dict

if sys.version_info < (3,):
    FileNotFoundError = IOError
    PermissionError = OSError
    FileExistsError = OSError


_SUPPORTED_WHEEL_VERSION = (1, 0)

_WHEEL_NAME_REGEX = re.compile(r'(?P<distribution>.+)-(?P<version>.+)'
                               r'(-(?P<build_tag>.+))?-(?P<python_tag>.+)'
                               r'-(?P<abi_tag>.+)-(?P<platform_tag>.+).whl')

logger = logging.getLogger('install')


class InstallException(Exception):
    pass


def _destdir_path(destdir, lib):  # type: (str, str) -> str
    path = sysconfig.get_path(lib)
    if not path:
        raise InstallException("Couldn't find {}".format(lib))
    return os.path.join(destdir, os.sep.join(path.split(os.sep)[1:]))


def _read_wheel_metadata(dist_info_path):  # type: (str) -> Dict[str, str]
    metadata = {}
    try:
        with open(os.path.join(dist_info_path, 'WHEEL')) as f:
            for line in f:
                entry = line.split(':')
                if len(entry) == 2:  # throw error?
                    metadata[entry[0].strip()] = entry[1].strip()
    except FileNotFoundError as e:
        raise InstallException("File '{}' not found".format(e.filename))
    except PermissionError as e:
        raise InstallException("{}: '{}' ".format(e.strerror, e.filename))
    return metadata


def parse_name(name):  # type: (str) -> Dict[str, str]
    match = _WHEEL_NAME_REGEX.match(name)
    if not match:
        raise InstallException('Invalid wheel name: {}'.format(name))
    return match.groupdict()


def build(wheel, cache_dir, optimize=[0, 1, 2]):  # type: (str, str, List[int]) -> None
    pkg_cache_dir = os.path.join(cache_dir, 'pkg')
    wheel_info = parse_name(os.path.basename(wheel))
    dist_info = os.path.join(pkg_cache_dir, '{}-{}.dist-info'.format(wheel_info['distribution'], wheel_info['version']))

    try:
        with zipfile.ZipFile(wheel) as wheel_zip:
            wheel_zip.extractall(pkg_cache_dir)
    except FileNotFoundError as e:
        raise InstallException("File '{}' not found".format(e.filename))
    except PermissionError as e:
        raise InstallException("{}: '{}' ".format(e.strerror, e.filename))
    except (ValueError, RuntimeError) as e:
        raise InstallException(str(e))

    metadata = _read_wheel_metadata(dist_info)

    if tuple(map(int, metadata['Wheel-Version'].split('.'))) > _SUPPORTED_WHEEL_VERSION:
        raise InstallException('Unsupported wheel version: {}'.format(metadata['Wheel-Version']))

    if sys.version_info >= (3,):
        for level in optimize:
            logger.debug('Optimizing for {}'.format(level))
            compileall.compile_dir(pkg_cache_dir, optimize=level)
    elif optimize:
        compileall.compile_dir(pkg_cache_dir)

    with open(os.path.join(cache_dir, 'wheel-info.pickle'), 'wb') as f:
        pickle.dump(wheel_info, f)
    with open(os.path.join(cache_dir, 'metadata.pickle'), 'wb') as f:
        pickle.dump(metadata, f)

    # TODO: verify checksums
    # TODO: generate entrypoint scripts


def install(cache_dir, destdir, user=False):  # type: (str, str, bool) -> None  # noqa: C901
    def destdir_path(lib):  # type: (str) -> str
        return _destdir_path(destdir, lib)

    with open(os.path.join(cache_dir, 'wheel-info.pickle'), 'rb') as f:
        wheel_info = pickle.load(f)
    with open(os.path.join(cache_dir, 'metadata.pickle'), 'rb') as f:
        metadata = pickle.load(f)

    pkg_cache_dir = os.path.join(cache_dir, 'pkg')
    pkg_data_dir_name = '{}-{}.data'.format(wheel_info['distribution'], wheel_info['version'])
    pkg_data_dir = os.path.join(cache_dir, pkg_data_dir_name)

    if user:
        pkg_dir = site.getusersitepackages()
    else:
        pkg_dir = destdir_path('purelib' if metadata['Root-Is-Purelib'] == 'true' else 'platlib')

    try:
        if sys.version_info >= (3, 8):
            shutil.copytree(pkg_cache_dir, pkg_dir, dirs_exist_ok=True,
                            ignore=lambda *_: ['purelib', 'platlib', pkg_data_dir_name])
            for lib in ['purelib', 'platlib']:
                target = os.path.join(pkg_cache_dir, lib)
                if os.path.isdir(target):
                    shutil.copytree(target, destdir_path(lib), dirs_exist_ok=True)
        else:
            from distutils.dir_util import copy_tree
            for node in os.listdir(pkg_cache_dir):
                for lib in ['purelib', 'platlib']:
                    if node == lib:
                        copy_tree(path, destdir_path(lib))
                        continue
                root = os.path.join(pkg_dir, node)
                path = os.path.join(pkg_cache_dir, node)
                if node == pkg_data_dir_name:
                    continue
                if os.path.isdir(path):
                    copy_tree(path, root)
                else:
                    shutil.copy2(path, root)
    except FileExistsError as e:
        raise InstallException("{}: '{}' ".format(e.strerror, e.filename))
