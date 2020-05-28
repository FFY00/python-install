# SPDX-License-Identifier: MIT

import argparse
import compileall
import os
import shutil
import site
import sys
import zipfile

_VERBOSE = False


def _error(msg, code=1):  # type: (str, int) -> None
    prefix = 'ERROR'
    if sys.stdout.isatty():
        prefix = '\33[91m' + prefix + '\33[0m'
    print('{} {}'.format(prefix, msg))
    exit(code)


def _verbose(msg):  # type: (str) -> None
    if _VERBOSE:
        prefix = suffix = ''
        if sys.stdout.isatty():
            prefix = '\33[2m'
            suffix = '\33[0m'
        print(prefix + msg + suffix)


if __name__ == '__main__':  # noqa: C901
    sys.argv[0] = 'python -m install'
    parser = argparse.ArgumentParser()
    parser.add_argument('wheel', nargs='?',
                        type=str,
                        help='wheel file to install')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='enable verbose output')
    parser.add_argument('--user', '-u',
                        action='store_true',
                        help='install as user')
    parser.add_argument('--optimize', '-o', nargs='*', metavar='level',
                        type=int, default=[0, 1, 2],
                        help='optimization level(s) (default=0, 1, 2)')
    parser.add_argument('--destdir', '-d', metavar='/',
                        type=str, default='/',
                        help='destination directory')
    # build/install separation
    parser.add_argument('--cache', '-c',
                        action='store_true',
                        help='generate the installation cache')
    parser.add_argument('--skip-build', '-s',
                        action='store_true',
                        help='skip the cache building step, requires cache to be present already')
    args = parser.parse_args()

    _VERBOSE = args.verbose

    cache_dir = '.install-cache'
    pkg_cache_dir = os.path.join(cache_dir, 'pkg')
    entrypoints_cache_dir = os.path.join(cache_dir, 'entrypoints')

    if args.cache and args.skip_build:
        _error("--cache and --skip-build can't be used together, choose one")

    if not args.wheel and not args.skip_build:
        _error('Missing argument: wheel')

    if os.path.exists(cache_dir):
        if os.path.isdir(cache_dir):
            if not args.skip_build:
                _verbose('Cache directory exists, removing')
                shutil.rmtree(cache_dir)
        else:
            _error("The cache path ('{}') exists and it's not a directory".format(cache_dir))

    # Build cache
    if not args.skip_build:
        try:
            with zipfile.ZipFile(args.wheel) as wheel:
                wheel.extractall(pkg_cache_dir)
        except FileNotFoundError as e:
            _error("File '{}' not found".format(e.filename))
        except PermissionError as e:
            _error("{}: '{}' ".format(e.strerror, e.filename))
        except (ValueError, RuntimeError) as e:
            _error(str(e))

        for level in args.optimize:
            _verbose('Optimizing for {}'.format(level))
            compileall.compile_dir(pkg_cache_dir, optimize=level)

        # TODO: verify checksums
        # TODO: generate entrypoint scripts

    # Install to destination
    if not args.cache:
        if not os.path.isdir(cache_dir):
            _error('Missing installation cache (hint: python -m install --cache [ ... ])')

        if args.user:
            pkg_dir = site.getusersitepackages()
        else:
            # TODO: allow selecting one of the valid paths?
            pkg_dir = site.getsitepackages()[0]

        pkg_dir = os.path.join(args.destdir, os.sep.join(pkg_dir.split(os.sep)[1:]))

        try:
            if sys.version_info >= (3, 8):
                shutil.copytree(pkg_cache_dir, pkg_dir, dirs_exist_ok=True)
            else:
                from distutils.dir_util import copy_tree
                copy_tree(pkg_cache_dir, pkg_dir)
        except FileExistsError as e:
            _error("{}: '{}' ".format(e.strerror, e.filename))
