#!/usr/bin/env python
"""
Tests for selected deprecated functions 
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import shutil
import unittest
import time
from testCommon import testEupsStack
from cStringIO import StringIO

from eups import TagNotRecognized, Product, ProductNotFound, EupsException
from eups.Eups import Eups
from eups.stack import ProductStack
from eups.utils import Quiet

syserr = sys.stderr

class DeprecatedTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_USERDATA"] = os.path.join(testEupsStack,"_userdata_")
        self.dbpath = os.path.join(testEupsStack, "ups_db")

        self._resetOut()

    def _resetOut(self):
        self.err = StringIO()
        sys.stderr = self.err

    def tearDown(self):
        sys.stderr = syserr

    def testDeprecatedProduct(self):
        prod = Product(Eups(), "newprod", noInit=True)
        self.assert_(prod is not None)
        self.assert_(self.err.getvalue().find("deprecated") >= 0)

        self.assertEqual(prod.envarDirName(), "NEWPROD_DIR")
        self.assertEqual(prod.envarSetupName(), "SETUP_NEWPROD")



__all__ = "DeprecatedTestCase".split()        

if __name__ == "__main__":
    unittest.main()
