#!/usr/bin/env python
"""
Tests for selected app functions.  Note that functions from the eups.app 
module are imported into the eups module.  Note also the most of these 
functions are tested via testCmd.py
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import shutil
import unittest
import time
from testCommon import testEupsStack

import eups

class AppTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        self.dbpath = os.path.join(testEupsStack, "ups_db")

    def tearDown(self):
        if os.environ.has_key("PYTHON_DIR"):
            eups.unsetup("python")

    def testSetup(self):
        t = eups.Setup()
        self.assert_(isinstance(t, eups.Tag), "Setup() did not return a Tag")
        self.assertEquals(str(t), "setup")

    def testProductDir(self):
        if os.environ.has_key("PYTHON_DIR"):
            del os["PYTHON_DIR"]
        if os.environ.has_key("SETUP_PYTHON"):
            del os["SETUP_PYTHON"]

        self.assert_(eups.productDir("python") is None, 
                     "found unsetup product")

        pdir = os.path.join(testEupsStack, os.environ["EUPS_FLAVOR"], 
                            "python", "2.5.2")
        dir = eups.productDir("python", "2.5.2")
        self.assertEquals(dir, pdir)

        eups.setup("python", "2.5.2")
        dir = eups.productDir("python")
        self.assertEquals(dir, pdir)

    def testGetSetupVersion(self):
        self.assertRaises(eups.ProductNotFound, eups.getSetupVersion, "python")

        eups.setup("python", "2.5.2")
        version = eups.getSetupVersion("python")
        self.assertEquals(version, "2.5.2")


__all__ = "AppTestCase".split()        

if __name__ == "__main__":
    unittest.main()



    
