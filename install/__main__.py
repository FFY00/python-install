# SPDX-License-Identifier: MIT

import argparse
import logging
import os
import shutil
import sys
import traceback

from . import build, install, InstallException


logger = logging.getLogger('install.main')


def _error(msg, code=1):  # type: (str, int) -> None
    prefix = 'ERROR'
    if sys.stdout.isatty():
        prefix = '\33[91m' + prefix + '\33[0m'
    print('{} {}'.format(prefix, msg))
    exit(code)


if __name__ == '__main__':  # noqa: C901
    sys.argv[0] = 'python -m install'
    parser = argparse.ArgumentParser()
    parser.add_argument('wheel', nargs='?',
                        type=str,
                        help='wheel file to install')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='enable verbose output')
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

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

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
                logger.debug('Cache directory exists, removing')
                shutil.rmtree(cache_dir)
        else:
            _error("The cache path ('{}') exists and it's not a directory".format(cache_dir))

    # Build cache
    if not args.skip_build:
        try:
            build(args.wheel, cache_dir, args.optimize)
        except InstallException as e:
            _error(str(e))
        except Exception as e:
            print(traceback.format_exc())
            _error(str(e))

    # Install to destination
    if not args.cache:
        if not os.path.isdir(cache_dir):
            _error('Missing installation cache (hint: python -m install --cache [ ... ])')

        try:
            install(cache_dir, args.destdir)
        except InstallException as e:
            _error(str(e))
        except Exception as e:
            print(traceback.format_exc())
            _error(str(e))
