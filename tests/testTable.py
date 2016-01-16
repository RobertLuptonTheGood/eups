#!/usr/bin/env python
"""
Tests for eups.product
"""

import os
import unittest
import testCommon
from testCommon import testEupsStack

from eups.table import Table
from eups.Eups import Eups

class TableTestCase1(unittest.TestCase):
    """test the Table class"""

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.tablefile = os.path.join(testEupsStack, "mwi.table")
        self.table = Table(self.tablefile)

    def testInit(self):
        self.assertEquals(self.table.file, self.tablefile)
        # Note: we add one to account for the default product
        self.assertEquals(len(self.table.actions("Darwin")), 14)
        self.assertEquals(len(self.table.actions("Linux")), 13)
        self.assertEquals(len(self.table.actions("Linux+2.1.2")), 14)
        self.assertEquals(len(self.table.actions("DarwinX86")), 14)

class TableTestCase2(unittest.TestCase):
    """test the Table class"""

    def setUp(self):
        self.environ0 = os.environ.copy()
        os.environ["EUPS_PATH"] = testEupsStack
        self.tablefile = os.path.join(testEupsStack, "tablesyntax.table")
        self.table = Table(self.tablefile)
        self.eups = Eups(flavor="Linux")
        for k in ["EIGEN_DIR",]:        # we're going to assert that it isn't set
            try:
                del os.environ[k]
            except KeyError:
                pass

    def tearDown(self):
        os.environ = self.environ0

    def testNoSetup(self):
        actions = self.table.actions("Linux")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assertIn("GOOBPATH", os.environ)
        self.assertEquals(os.environ["GOOBPATH"], 
                          "/home/user/goob:/usr/goob:/usr/local/goob")
        self.assertNotIn("FOO", os.environ)
        self.assertNotIn("BAR", os.environ)
        self.assertIn("longls", self.eups.aliases)
        self.assertEquals(self.eups.aliases["longls"], "ls -l")

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assertNotIn("FOO", os.environ)
        self.assertNotIn("BAR", os.environ)
        self.assertIn("GOOBPATH", os.environ)
        self.assertEquals(os.environ["GOOBPATH"], '')

    def testIfFlavor(self):
        actions = self.table.actions("DarwinX86")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assertIn("GOOBPATH", os.environ)
        self.assertIn("FOO", os.environ)
        self.assertEquals(os.environ["FOO"], "1")
        self.assertNotIn("BAR", os.environ)

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assertNotIn("FOO", os.environ)
        self.assertNotIn("BAR", os.environ)
        self.assertIn("GOOBPATH", os.environ)
        self.assertEquals(os.environ["GOOBPATH"], '')
        

    def testIfType(self):
        actions = self.table.actions("DarwinX86", "build")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assertIn("GOOBPATH", os.environ)
        self.assertIn("FOO", os.environ)
        self.assertEquals(os.environ["FOO"], "1")
        self.assertIn("BAR", os.environ)

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assertNotIn("FOO", os.environ)
        self.assertIn("GOOBPATH", os.environ)
        self.assertIn("BAR", os.environ)
        self.assertEquals(os.environ["GOOBPATH"], '')
        self.assertEquals(os.environ["BAR"], '')

    def testSetup(self):
        actions = self.table.actions("Linux")
        for action in actions:
            action.execute(self.eups, 1, True)
        self.assertIn("GOOBPATH", os.environ)
        self.assertIn("SETUP_PYTHON", os.environ)
        self.assertIn("PYTHON_DIR", os.environ)
        self.assertIn("CFITSIO_DIR", os.environ)
        self.assertNotIn("EIGEN_DIR", os.environ)

    def testEmptyBlock(self):
        actions = self.table.actions("Linux64")
        for action in actions:
            action.execute(self.eups, 1, True)
        self.assertIn("GOOBPATH", os.environ)
        self.assertNotIn("FOO", os.environ)
        self.assertNotIn("BAR", os.environ)

    def testEnvSetWithForce(self):
        """ensure use of force does not cause failure"""
        actions = self.table.actions("Linux")
        self.eups.force = True

        # the following will fail if bug referred to in [11454] exists
        for action in actions:
            action.execute(self.eups, 1, True)


class EmptyTableTestCase(unittest.TestCase):
    """
    test out an (effectively) empty table file
    """
    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.tablefile = os.path.join(testEupsStack, "empty.table")
        self.table = Table(self.tablefile)
        self.eups = Eups()

    def testEmptyBlock(self):
        actions = self.table.actions("Linux64")
        for action in actions:
            action.execute(self.eups, 1, True)

class IfElseTestCase(unittest.TestCase):
    """
    Check that if ... else if ... else blocks work
    """
    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.tablefile = os.path.join(testEupsStack, "ifElse.table")
        self.table = Table(self.tablefile)
        self.eups = Eups()

    def testEmptyBlock(self):
        for t in ("sdss", "sst", ""):
            actions = self.table.actions(None, t)
            for action in actions:
                action.execute(self.eups, 1, True)

            if not t:
                t = "other"

            self.assertEqual(os.environ["FOO"].lower(), t)
                

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        EmptyTableTestCase,
        TableTestCase1,
        TableTestCase2,
        IfElseTestCase,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
