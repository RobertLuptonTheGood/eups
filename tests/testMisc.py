#!/usr/bin/env python
"""
Miscellaneous Tests.  These might eventually be migrated into other test
files.
"""
import os
import sys
import shutil
import re
import unittest
import time
import testCommon
from testCommon import testEupsStack

import eups

class MiscTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testNothing(self):
        pass

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        MiscTestCase,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
