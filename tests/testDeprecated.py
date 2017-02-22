#!/usr/bin/env python
"""
Tests for selected deprecated functions
"""

import os
import sys
import unittest
import testCommon
from testCommon import testEupsStack
from eups.utils import StringIO

# reroute the error stream defined in eups.util to newerr
syserr = sys.stderr
newerr = StringIO.StringIO()
sys.stderr = newerr
import eups.utils
eups.utils.reload(eups.utils)
sys.stderr = syserr

from eups.Product import Product
from eups.Eups import Eups


class DeprecatedTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_USERDATA"] = os.path.join(testEupsStack,"_userdata_")
        self.dbpath = os.path.join(testEupsStack, "ups_db")

        self._resetOut()

    def _resetOut(self):
        newerr.seek(0)
        newerr.truncate()
        # sys.stderr = newerr

    def tearDown(self):
        os.environ = self.environ0
        # sys.stderr = syserr

    def testDeprecatedProduct(self):
        prod = Product(Eups(), "newprod", noInit=True)
        self.assert_(prod is not None)
        self.assert_(newerr.getvalue().find("deprecated") >= 0)

        self.assertEqual(prod.envarDirName(), "NEWPROD_DIR")
        self.assertEqual(prod.envarSetupName(), "SETUP_NEWPROD")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        DeprecatedTestCase,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
