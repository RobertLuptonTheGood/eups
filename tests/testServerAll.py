#!/usr/bin/env python
"""
A master script for running all tests.
"""
import sys, unittest
from testServerLocal import *

if False:
    from testServerWeb import *
    from testServerSsh import *
else:
    print >> sys.stderr, "The remote server tests rely on a server that used to run on lsstcorp.org; skipping"

if __name__ == "__main__":
    unittest.main()
