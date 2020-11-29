# SPDX-License-Identifier: MIT

import os.path
import sys


sys.path.insert(0, os.path.abspath(
    os.path.join(__file__, '..', 'installer', 'src')
))


print(sys.path)
