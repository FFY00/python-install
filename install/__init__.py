# SPDX-License-Identifier: MIT

import compileall
import logging
import os
import site
import shutil
import sys
import sysconfig
import zipfile

from typing import List


'''
python-install - A simple, correct PEP427 wheel installer
'''
__version__ = '0.0.1'


logger = logging.getLogger('install')


class InstallException(Exception):
    pass


def _destdir_path(destdir, lib):  # type: (str, str) -> str
    path = sysconfig.get_path(lib)
    if not path:
        raise InstallException("Couldn't find {}".format(lib))
    return os.path.join(destdir, os.sep.join(path.split(os.sep)[1:]))


def build(wheel, cache_dir, optimize):  # type: (str, str, List[int]) -> None
    pkg_cache_dir = os.path.join(cache_dir, 'pkg')

    try:
        with zipfile.ZipFile(wheel) as wheel_zip:
            wheel_zip.extractall(pkg_cache_dir)
    except FileNotFoundError as e:
        raise InstallException("File '{}' not found".format(e.filename))
    except PermissionError as e:
        raise InstallException("{}: '{}' ".format(e.strerror, e.filename))
    except (ValueError, RuntimeError) as e:
        raise InstallException(str(e))

    for level in optimize:
        logger.debug('Optimizing for {}'.format(level))
        compileall.compile_dir(pkg_cache_dir, optimize=level)

    # TODO: verify checksums
    # TODO: generate entrypoint scripts


def install(cache_dir, destdir, user=False):  # type: (str, str, bool) -> None  # noqa: C901
    pkg_cache_dir = os.path.join(cache_dir, 'pkg')

    def destdir_path(lib):  # type: (str) -> str
        return _destdir_path(destdir, lib)

    if user:
        pkg_dir = site.getusersitepackages()
    else:
        pkg_dir = destdir_path('purelib')  # TODO: read metadata and use the correct lib

    try:
        if sys.version_info >= (3, 8):
            shutil.copytree(pkg_cache_dir, pkg_dir, dirs_exist_ok=True, ignore=lambda *_: ['purelib', 'platlib'])
            for lib in ['purelib', 'platlib']:
                target = os.path.join(pkg_cache_dir, lib)
                if os.path.isdir(target):
                    shutil.copytree(target, destdir_path(lib), dirs_exist_ok=True)
        else:
            from distutils.dir_util import copy_tree
            root = os.path.join(pkg_dir, os.path.basename(pkg_cache_dir))
            for node in os.listdir(pkg_cache_dir):
                path = os.path.join(pkg_cache_dir, node)
                for lib in ['purelib', 'platlib']:
                    if node == lib:
                        copy_tree(path, destdir_path(lib))
                        continue
                if os.path.isdir(path):
                    copy_tree(path, root)
                else:
                    shutil.copy2(path, root)
    except FileExistsError as e:
        raise InstallException("{}: '{}' ".format(e.strerror, e.filename))
