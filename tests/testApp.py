#!/usr/bin/env python
"""
Tests for selected app functions.  Note that functions from the eups.app 
module are imported into the eups module.  Note also the most of these 
functions are tested via testCmd.py
"""

import os
import shutil
import unittest
from eups.utils import StringIO
import testCommon
from testCommon import testEupsStack

import eups

class AppTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()
        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        if eups.Eups().isSetup("python"):
            eups.unsetup("python")
        self.dbpath = os.path.join(testEupsStack, "ups_db")

    def tearDown(self):
        os.environ = self.environ0

    def testProductDir(self):
        if "PYTHON_DIR" in os.environ:
            del os.environ["PYTHON_DIR"]
        if "SETUP_PYTHON" in os.environ:
            del os.environ["SETUP_PYTHON"]

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

class TagSetupTestCase(unittest.TestCase):
    """
    Tests use cases for selecting tagged versions via app.setup()
    """
    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_USERDATA"] = os.path.join(testEupsStack,"_userdata_")
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.eups = eups.Eups(quiet=1)
        self.eups.quiet = 0
        self.eups.unsetupSetupProduct("python")

        self.eups.tags.registerTag("beta")
        self.eups.tags.registerUserTag("rhl")

    def tearDown(self):
        self.eups.unsetupSetupProduct("python")
        self.eups.unsetupSetupProduct("newprod")

        if (self.eups.findProduct("python", "test")):
            self.eups.undeclare("python", "test")
        if (self.eups.findProduct("python", "rhl")):
            self.eups.undeclare("python", "rhl")

        eups.clearCache(inUserDir=True)
        eups.clearCache(inUserDir=False)
        del self.eups

        pdbdir = os.path.join(self.dbpath, "newprod")
        if os.path.exists(pdbdir):
            shutil.rmtree(pdbdir)
        userdir = os.path.join(testEupsStack,"_userdata_")
        if os.path.exists(userdir):
            shutil.rmtree(userdir)
        chainfile = os.path.join(self.dbpath, "python", "beta.chain")
        if os.path.exists(chainfile):
            os.remove(chainfile)
        chainfile = os.path.join(self.dbpath, "python", "rhl.chain")
        if os.path.exists(chainfile):
            os.remove(chainfile)
        chainfile = os.path.join(self.dbpath, "python", "rhl.chain")
        if os.path.exists(chainfile):
            os.remove(chainfile)

    def testDefPrefTag(self):
        """
        test equivalent to "setup prod"
        """
        # test some assumptions
        preftags = self.eups.getPreferredTags()
        self.assertIn("current", preftags, "no python marked current")
        self.assertNotIn("SETUP_PYTHON", os.environ, "python already set")

        # setup the preferred (tagged current) version
        eups.setup("python")
        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "2.5.2")
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

        # check for dependent product
        prod = self.eups.findSetupProduct("tcltk")
        self.assert_(prod is not None, "tcltk not setup")
        self.assertEquals(prod.version, "8.5a4")
        self.assertIn("SETUP_TCLTK", os.environ, "SETUP_TCLTK not set")
        self.assertIn("TCLTK_DIR", os.environ, "TCLTK_DIR not set")
        self.assertEquals(os.environ["TCLTK_DIR"], prod.dir)        

        eups.unsetup("python")
        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is None, "python is still setup")
        self.assertNotIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON is still set")
        self.assertNotIn("PYTHON_DIR", os.environ, "PYTHON_DIR is still set")
        prod = self.eups.findSetupProduct("tcltk")
        self.assert_(prod is None, "tcltk is still setup")
        self.assertNotIn("SETUP_TCLTK", os.environ, "SETUP_TCLTK is still set")
        self.assertNotIn("TCLTK_DIR", os.environ, "TCLTK_DIR is still set")

        # set up an explicit version
        eups.setup("python", "2.5.2")
        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "2.5.2")
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

        # check for dependent product
        prod = self.eups.findSetupProduct("tcltk")
        self.assert_(prod is not None, "tcltk not setup")
        self.assertEquals(prod.version, "8.5a4")
        self.assertIn("SETUP_TCLTK", os.environ, "SETUP_TCLTK not set")
        self.assertIn("TCLTK_DIR", os.environ, "TCLTK_DIR not set")
        self.assertEquals(os.environ["TCLTK_DIR"], prod.dir)        

        eups.unsetup("python")
        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is None, "python is still setup")
        self.assertNotIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON is still set")
        self.assertNotIn("PYTHON_DIR", os.environ, "PYTHON_DIR is still set")
        prod = self.eups.findSetupProduct("tcltk")
        self.assert_(prod is None, "tcltk is still setup")
        self.assertNotIn("SETUP_TCLTK", os.environ, "SETUP_TCLTK is still set")
        self.assertNotIn("TCLTK_DIR", os.environ, "TCLTK_DIR is still set")


    def testTaggedTarget(self):
        """
        test equivalent to "setup --tag mine prod" where prod is tagged "mine"
        """

        # do some setup for this test
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "1.0")
        pdbdir = os.path.join(self.dbpath, "newprod")
        pupsdir = os.path.join(pdbdir, "Linux")
        ptble10 = os.path.join(pupsdir, "1.0.table")
        ptble20 = os.path.join(pupsdir, "2.0.table")
        newprodtable = \
"""
setupRequired(python)
"""
        self.eups.declare("newprod", "1.0", pdir10, testEupsStack, 
                          tablefile=StringIO(newprodtable))
        self.eups.declare("newprod", "2.0", pdir20, testEupsStack, 
                          tablefile=StringIO(newprodtable), tag="beta")
        # test the setup
        self.assert_(self.eups.findProduct("newprod", "1.0") is not None, "newprod 1.0 not declared")
        self.assert_(self.eups.findProduct("newprod", "2.0") is not None, "newprod 2.0 not declared")
        self.assert_(os.path.exists(ptble10), "Can't find newprod 1.0's table file")
        self.assert_(os.path.exists(ptble20), "Can't find newprod 2.0's table file")

        self.assertEquals(len(filter(lambda p: p[0] == "newprod", self.eups.uses("python"))), 2,
                          "newprod does not depend on python")

        # now we are ready to go: request the beta version of newprod
        eups.setup("newprod", prefTags="beta")

        prod = self.eups.findSetupProduct("newprod")
        self.assert_(prod is not None, "newprod not setup")
        self.assertEquals(prod.version, "2.0")
        self.assertIn("SETUP_NEWPROD", os.environ, "SETUP_NEWPROD not set")
        self.assertIn("NEWPROD_DIR", os.environ, "NEWPROD_DIR not set")
        self.assertEquals(os.environ["NEWPROD_DIR"], pdir20)

        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "2.5.2")  # tagged current 
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

        eups.unsetup("newprod")
        prod = self.eups.findSetupProduct("newprod")
        self.assert_(prod is None, "newprod is still setup")
        self.assertNotIn("SETUP_NEWPROD", os.environ, "SETUP_NEWPROD not set")
        self.assertNotIn("NEWPROD_DIR", os.environ, "NEWPROD_DIR not set")
        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is None, "python is still setup")
        self.assertNotIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON is still set")
        self.assertNotIn("PYTHON_DIR", os.environ, "PYTHON_DIR is still set")

        # now test with dependent product with requested tag
        self.eups.assignTag("beta", "python", "2.6")
        eups.setup("newprod", prefTags="beta")

        prod = self.eups.findSetupProduct("newprod")
        self.assert_(prod is not None, "newprod not setup")
        self.assertEquals(prod.version, "2.0")
        self.assertIn("SETUP_NEWPROD", os.environ, "SETUP_NEWPROD not set")
        self.assertIn("NEWPROD_DIR", os.environ, "NEWPROD_DIR not set")
        self.assertEquals(os.environ["NEWPROD_DIR"], pdir20)

        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "2.6")  # tagged beta
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

        self.eups.unassignTag("beta", "python")


    def testTaggedDeps(self):
        """
        test equivalent to "setup --tag mine prod" where dependency is tagged "mine"
        """
        # do some setup for this test
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "1.0")
        pdbdir = os.path.join(self.dbpath, "newprod")
        pupsdir = os.path.join(pdbdir, "Linux")
        ptble10 = os.path.join(pupsdir, "1.0.table")
        ptble20 = os.path.join(pupsdir, "2.0.table")
        newprodtable = \
"""
setupRequired(python)
"""
        self.eups.declare("newprod", "1.0", pdir10, testEupsStack, 
                          tablefile=StringIO(newprodtable), tag="current")
        self.eups.declare("newprod", "2.0", pdir20, testEupsStack, 
                          tablefile=StringIO(newprodtable))
        self.eups.assignTag("beta", "python", "2.6")

        # test the setup
        self.assert_(self.eups.findProduct("newprod", "1.0") is not None, "newprod 1.0 not declared")
        self.assert_(self.eups.findProduct("newprod", "2.0") is not None, "newprod 2.0 not declared")
        self.assert_(os.path.exists(ptble10), "Can't find newprod 1.0's table file")
        self.assert_(os.path.exists(ptble20), "Can't find newprod 2.0's table file")

        self.assertEquals(len(filter(lambda p: p[0] == "newprod", self.eups.uses("python"))), 2,
                          "newprod does not depend on python")

        # now we are ready to go: request the beta version of newprod
        q = eups.Quiet(self.eups)
        eups.setup("newprod", prefTags="beta", eupsenv=self.eups)
        del q

        prod = self.eups.findSetupProduct("newprod")
        self.assert_(prod is not None, "newprod not setup")
        self.assertEquals(prod.version, "1.0")
        self.assertIn("SETUP_NEWPROD", os.environ, "SETUP_NEWPROD not set")
        self.assertIn("NEWPROD_DIR", os.environ, "NEWPROD_DIR not set")
        self.assertEquals(os.environ["NEWPROD_DIR"], pdir20)

        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "2.6")  # tagged beta
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

    def testTaggedDeps2(self):
        """
        test equivalent to "setup --tag mine prod" where dependency is tagged "mine"
        """
        # do some setup for this test
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "1.0")
        pdbdir = os.path.join(self.dbpath, "newprod")
        pupsdir = os.path.join(pdbdir, "Linux")
        ptble10 = os.path.join(pupsdir, "1.0.table")
        ptble20 = os.path.join(pupsdir, "2.0.table")
        newprodtable = \
"""
setupRequired(python 2.5.2 [>= 2.5])
"""
        pyprod = self.eups.getProduct("python", "2.5.2")
        pytdir = pyprod.dir

        self.eups.declare("newprod", "1.0", pdir10, testEupsStack, 
                          tablefile=StringIO(newprodtable), tag="current")
        self.eups.declare("newprod", "2.0", pdir20, testEupsStack, 
                          tablefile=StringIO(newprodtable))
        self.eups.declare("python", "test", pytdir, testEupsStack)
        self.eups.assignTag("rhl", "python", "test")

        # test the setup
        self.assert_(self.eups.findProduct("newprod", "1.0") is not None, "newprod 1.0 not declared")
        self.assert_(self.eups.findProduct("newprod", "2.0") is not None, "newprod 2.0 not declared")
        self.assert_(os.path.exists(ptble10), "Can't find newprod 1.0's table file")
        self.assert_(os.path.exists(ptble20), "Can't find newprod 2.0's table file")
        self.assert_(self.eups.findProduct("python", "test") is not None, "python test not declared")

        self.assertEquals(len(filter(lambda p: p[0] == "newprod", self.eups.uses("python"))), 2,
                          "newprod does not depend on python")

        # now we are ready to go: request the beta version of newprod
        q = eups.Quiet(self.eups)
        eups.setup("newprod", prefTags="rhl", eupsenv=self.eups)
        del q

        prod = self.eups.findSetupProduct("newprod")
        self.assert_(prod is not None, "newprod not setup")
        self.assertEquals(prod.version, "1.0")
        self.assertIn("SETUP_NEWPROD", os.environ, "SETUP_NEWPROD not set")
        self.assertIn("NEWPROD_DIR", os.environ, "NEWPROD_DIR not set")
        self.assertEquals(os.environ["NEWPROD_DIR"], pdir20)

        prod = self.eups.findSetupProduct("python")
        self.assert_(prod is not None, "python not setup")
        self.assertEquals(prod.version, "test")  # tagged rhl
        self.assertIn("SETUP_PYTHON", os.environ, "SETUP_PYTHON not set")
        self.assertIn("PYTHON_DIR", os.environ, "PYTHON_DIR not set")
        self.assertEquals(os.environ["PYTHON_DIR"], prod.dir)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([AppTestCase], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
