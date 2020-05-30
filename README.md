# python-install

A simple, correct PEP427 wheel installer.

```sh
$ python -m install -h
usage: python -m install [-h] [--verbose] [--optimize [level [level ...]]] [--destdir /] [--cache] [--skip-build] [--ignore-incomplete-installation-warnings] [wheel]

positional arguments:
  wheel                 wheel file to install

optional arguments:
  -h, --help            show this help message and exit
  --verbose, -v         enable verbose output
  --optimize [level [level ...]], -o [level [level ...]]
                        optimization level(s) (default=0, 1, 2)
  --destdir /, -d /     destination directory
  --cache, -c           generate the installation cache
  --skip-build, -s      skip the cache building step, requires cache to be present already
  --ignore-incomplete-installation-warnings, -w
                        stop treating incomplete installation warnings as errors
```

Missing components:
  - Checksum verification
  - Custom data installation:
    - `headers`
    - `data`

### Bootstraping

`install` has a dependency on `installer`, which is used for entrypoint script
generation. As we don't install entrypoint scripts, this dependency is not needed
to install a `install` wheel, making `install` bootstrapable without any
dependencies.
