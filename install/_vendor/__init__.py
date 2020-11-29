# SPDX-License-Identifier: MIT

import sys
import os.path


sys.path.insert(0, os.path.abspath(
    os.path.join(__file__, '..', 'installer', 'src')
))


print(sys.path)
