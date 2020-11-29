# SPDX-License-Identifier: MIT

from __future__ import print_function

import compileall
import configparser
import fileinput
import logging
import os
import pickle
import platform
import py_compile
import re
import shutil
import sys
import sysconfig
import warnings
import zipfile

import install._vendor as _vendor  # noqa: F401


'''
python-install - A simple, correct PEP427 wheel installer
'''
__version__ = '0.0.3'


if sys.version_info >= (3, 5) or (sys.version_info < (3,) and sys.version_info >= (2, 7)):
    from typing import Any, Dict, List

if sys.version_info < (3,):
    FileNotFoundError = IOError
    PermissionError = OSError
    FileExistsError = OSError


_SUPPORTED_WHEEL_VERSION = (1, 0)

_WHEEL_NAME_REGEX = re.compile(r'(?P<distribution>.+)-(?P<version>.+)'
                               r'(-(?P<build_tag>.+))?-(?P<python_tag>.+)'
                               r'-(?P<abi_tag>.+)-(?P<platform_tag>.+).whl')

logger = logging.getLogger('install')


class IncompleteInstallationWarning(RuntimeWarning):
    '''
    Some installation step was not handled, potentially resulting in an
    incomplete instalation
    '''


class InstallWarning(RuntimeWarning):
    pass


class InstallException(Exception):
    pass


def _destdir_path(destdir, lib):  # type: (str, str) -> str
    path = sysconfig.get_path(lib)
    if not path:
        raise InstallException("Couldn't find {}".format(lib))
    return os.path.join(destdir, os.sep.join(path.split(os.sep)[1:]))


def _read_wheel_metadata(dist_info_path):  # type: (str) -> Dict[str, str]
    metadata = {}
    with open(os.path.join(dist_info_path, 'WHEEL')) as f:
        for line in f:
            entry = line.split(':')
            if len(entry) == 2:  # throw error?
                metadata[entry[0].strip()] = entry[1].strip()
    return metadata


if sys.version_info >= (3, 8):

    def _copy_dir(src, dst, ignore=[]):  # type: (str, str, List[str]) -> None
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=lambda *_: ignore)

else:

    def _copy_dir(src, dst, ignore=[]):  # type: (str, str, List[str]) -> None
        from distutils.dir_util import copy_tree
        for node in os.listdir(src):
            if node in ignore:
                continue
            path = os.path.join(src, node)
            root = os.path.join(dst, node)
            if os.path.isdir(path):
                copy_tree(path, root)
            else:
                shutil.copy2(path, root)


def _generate_entrypoint_scripts(file, dir):  # type: (str, str) -> None
    entrypoints = configparser.ConfigParser()
    entrypoints.read(file)
    if 'console_scripts' in entrypoints:
        if not os.path.exists(dir):
            os.mkdir(dir)

        import installer.scripts

        for name, backend in entrypoints['console_scripts'].items():
            package, call = backend.split(':')

            script = installer.scripts.Script(name, package, call, section='console')
            name, data = script.generate(sys.executable, kind='posix')

            with open(os.path.join(dir, name), 'wb') as f:
                f.write(data)


def _replace_shebang(dir, interpreter):  # type: (str, str) -> None
    scripts = [os.path.join(dir, script) for script in os.listdir(dir)]

    for script in scripts:
        if not os.path.isfile(script):
            raise InstallException('Script is not a file: {}'.format(script))

    # Python 2 does not support fileinput as a contex manager
    f = fileinput.input(scripts, inplace=True)
    for line in f:
        if f.isfirstline():
            line = re.sub(r'^#!python', '#!{}'.format(interpreter), line)
        print(line, end='')
    f.close()


def _check_requirement(requirement_string):  # type: (str) -> bool
    import packaging.requirements

    if sys.version_info >= (3, 8):
        from importlib import metadata as importlib_metadata
    else:
        import importlib_metadata

    req = packaging.requirements.Requirement(requirement_string)

    if req.marker and not req.marker.evaluate():
        return True

    try:
        version = importlib_metadata.version(req.name)
        metadata = importlib_metadata.metadata(req.name)
    except importlib_metadata.PackageNotFoundError:
        return False

    metadata_extras = metadata.get_all('Provides-Extra') or []
    for extra in req.extras:
        if extra not in metadata_extras:
            return False

    if req.specifier:
        return req.specifier.contains(version)

    return True


def _verify_compability(dir, verify_dependencies=False):  # type: (str, bool) -> None
    try:
        import packaging.specifiers

        if sys.version_info >= (3, 8):
            from importlib import metadata as importlib_metadata
        else:
            import importlib_metadata

        dist = importlib_metadata.Distribution.at(dir)

        py_ver = dist.metadata['Requires-Python']
        if py_ver:
            py_vers = py_ver.split(',')
            for ver in py_vers:
                py_spec = packaging.specifiers.Specifier(ver)
                if platform.python_version() not in py_spec:
                    raise InstallException('Incompatible python version, needed: {}'.format(py_ver))

        if verify_dependencies:
            for req in dist.metadata.get_all('Requires-Dist') or []:
                if not _check_requirement(req):
                    raise InstallException('Missing dependency: {}'.format(req))

    except ImportError as e:
        warnings.warn('{}: Platform/Python tags were not verified for compatibility'.format(e), InstallWarning)


def _save_pickle(dir, name, data):  # type: (str, str, Any) -> None
    with open(os.path.join(dir, name + '.pickle'), 'wb') as f:
        pickle.dump(data, f)


def _load_pickle(dir, name):  # type: (str, str) -> Any
    with open(os.path.join(dir, name + '.pickle'), 'rb') as f:
        return pickle.load(f)


def parse_name(name):  # type: (str) -> Dict[str, str]
    match = _WHEEL_NAME_REGEX.match(name)
    if not match:
        raise InstallException('Invalid wheel name: {}'.format(name))
    return match.groupdict()


def build(wheel, cache_dir, optimize=[0, 1, 2], verify_dependencies=False):  # type: (str, str, List[int], bool) -> None
    pkg_cache_dir = os.path.join(cache_dir, 'pkg')
    scripts_cache_dir = os.path.join(cache_dir, 'scripts')
    wheel_info = parse_name(os.path.basename(wheel))
    package = '{}-{}'.format(wheel_info['distribution'], wheel_info['version'])
    dist_info = os.path.join(pkg_cache_dir, '{}.dist-info'.format(package))
    entrypoints_file = os.path.join(dist_info, 'entry_points.txt')
    scripts_dir = os.path.join(pkg_cache_dir, '{}.data'.format(package), 'scripts')

    with zipfile.ZipFile(wheel) as wheel_zip:
        wheel_zip.extractall(pkg_cache_dir)

    metadata = _read_wheel_metadata(dist_info)

    if tuple(map(int, metadata['Wheel-Version'].split('.'))) > _SUPPORTED_WHEEL_VERSION:
        raise InstallException('Unsupported wheel version: {}'.format(metadata['Wheel-Version']))

    _verify_compability(dist_info, verify_dependencies)

    if sys.version_info >= (3,):
        for level in optimize:
            logger.debug('Optimizing for {}'.format(level))
            if sys.version_info >= (3, 7):
                compileall.compile_dir(pkg_cache_dir, optimize=level,
                                       invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
            else:
                compileall.compile_dir(pkg_cache_dir, optimize=level)
    elif optimize:
        compileall.compile_dir(pkg_cache_dir)

    if os.path.isfile(entrypoints_file):
        _generate_entrypoint_scripts(entrypoints_file, scripts_cache_dir)

    if os.path.isdir(scripts_dir):
        _replace_shebang(scripts_dir, sys.executable)

    _save_pickle(cache_dir, 'wheel-info', wheel_info)
    _save_pickle(cache_dir, 'metadata', metadata)

    # TODO: verify checksums


def install(cache_dir, destdir):  # type: (str, str) -> None
    def destdir_path(lib):  # type: (str) -> str
        return _destdir_path(destdir, lib)

    wheel_info = _load_pickle(cache_dir, 'wheel-info')
    metadata = _load_pickle(cache_dir, 'metadata')

    pkg_cache_dir = os.path.join(cache_dir, 'pkg')
    scripts_cache_dir = os.path.join(cache_dir, 'scripts')
    pkg_data_dir_name = '{}-{}.data'.format(wheel_info['distribution'], wheel_info['version'])
    pkg_data_dir = os.path.join(cache_dir, pkg_data_dir_name)

    pkg_dir = destdir_path('purelib' if metadata['Root-Is-Purelib'] == 'true' else 'platlib')

    _copy_dir(pkg_cache_dir, pkg_dir, ignore=['purelib', 'platlib', pkg_data_dir_name])
    for lib in ['purelib', 'platlib']:
        target = os.path.join(pkg_cache_dir, lib)
        if os.path.isdir(target):
            _copy_dir(target, destdir_path(lib))
    if os.path.isdir(pkg_data_dir):
        for node in os.listdir(pkg_data_dir):
            target = os.path.join(pkg_cache_dir, node)
            if node == 'purelib':
                _copy_dir(target, destdir_path('purelib'))
            if node == 'platlib':
                _copy_dir(target, destdir_path('platlib'))
            if node == 'scripts':
                _copy_dir(target, destdir_path('scripts'))
            # TODO: headers, data -- is this a direct mapping to sysconfig? does it need specific path handling?
            else:
                warnings.warn('Unhandled data folder: {}'.format(node), IncompleteInstallationWarning)

    if os.path.isdir(scripts_cache_dir):
        _copy_dir(scripts_cache_dir, destdir_path('scripts'))
    # TODO: update dist-info/RECORD
