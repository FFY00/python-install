# python-install

A simple, correct PEP427 wheel installer.

```sh
$ python -m install -h
usage: python -m install [-h] [--verbose] [--optimize [level [level ...]]] [--destdir /] [--cache] [--skip-build] [wheel]

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
```

Missing components:
  - Checksum verification
  - Entrypoint scripts generation
  - Custom data installation:
    - `headers`
    - `data`
