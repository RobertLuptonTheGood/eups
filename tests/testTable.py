#!/usr/bin/env python
"""
Tests for eups.product
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import unittest
import time
from testCommon import testEupsStack

from eups.Product import Product, TableFileNotFound
from eups.table import Table, BadTableContent
from eups.Eups import Eups

class TableTestCase1(unittest.TestCase):
    """test the Table class"""

    def setUp(self):
        self.tablefile = os.path.join(testEupsStack, "mwi.table")
        self.table = Table(self.tablefile)

    def testInit(self):
        self.assertEquals(self.table.file, self.tablefile)
        self.assertEquals(len(self.table.actions("Darwin")), 13)
        self.assertEquals(len(self.table.actions("Linux")), 12)
        self.assertEquals(len(self.table.actions("Linux+2.1.2")), 13)
        self.assertEquals(len(self.table.actions("DarwinX86")), 13)

class TableTestCase2(unittest.TestCase):
    """test the Table class"""

    def setUp(self):
        self.tablefile = os.path.join(testEupsStack, "tablesyntax.table")
        self.table = Table(self.tablefile)
        self.eups = Eups()

    def tearDown(self):
        if os.environ.has_key("FOO"):
            del os.environ["FOO"]
        if os.environ.has_key("BAR"):
            del os.environ["BAR"]
        if os.environ.has_key("GOOBPATH"):
            del os.environ["GOOBPATH"]

    def testNoSetup(self):
        actions = self.table.actions("Linux")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assertEquals(os.environ["GOOBPATH"], 
                          "/home/user/goob:/usr/goob:/usr/local/goob")
        self.assert_(not os.environ.has_key("FOO"))
        self.assert_(not os.environ.has_key("BAR"))
        self.assert_(self.eups.aliases.has_key("longls"))
        self.assertEquals(self.eups.aliases["longls"], "ls -l")

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assert_(not os.environ.has_key("FOO"))
        self.assert_(not os.environ.has_key("BAR"))
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assertEquals(os.environ["GOOBPATH"], '')

    def testIfFlavor(self):
        actions = self.table.actions("DarwinX86")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assert_(os.environ.has_key("FOO"))
        self.assertEquals(os.environ["FOO"], "1")
        self.assert_(not os.environ.has_key("BAR"))

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assert_(not os.environ.has_key("FOO"))
        self.assert_(not os.environ.has_key("BAR"))
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assertEquals(os.environ["GOOBPATH"], '')
        

    def testIfType(self):
        actions = self.table.actions("DarwinX86", "build")
        for action in actions:
            action.execute(self.eups, 1, True, True)
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assert_(os.environ.has_key("FOO"))
        self.assertEquals(os.environ["FOO"], "1")
        self.assert_(os.environ.has_key("BAR"))

        # undo
        for action in actions:
            action.execute(self.eups, 1, False, True)
        self.assert_(not os.environ.has_key("FOO"))
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assert_(os.environ.has_key("BAR"))
        self.assertEquals(os.environ["GOOBPATH"], '')
        self.assertEquals(os.environ["BAR"], '')

    def testSetup(self):
        actions = self.table.actions("Linux")
        for action in actions:
            action.execute(self.eups, 1, True)
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assert_(os.environ.has_key("SETUP_PYTHON"))
        self.assert_(os.environ.has_key("PYTHON_DIR"))
        self.assert_(os.environ.has_key("CFITSIO_DIR"))
        self.assert_(not os.environ.has_key("EIGEN_DIR"))

    def testEmptyBlock(self):
        actions = self.table.actions("Linux64")
        for action in actions:
            action.execute(self.eups, 1, True)
        self.assert_(os.environ.has_key("GOOBPATH"))
        self.assert_(not os.environ.has_key("FOO"))
        self.assert_(not os.environ.has_key("BAR"))

class EmptyTableTestCase(unittest.TestCase):
    """
    test out an (effectively) empty table file
    """
    def setUp(self):
        self.tablefile = os.path.join(testEupsStack, "empty.table")
        self.table = Table(self.tablefile)
        self.eups = Eups()

    def testEmptyBlock(self):
        actions = self.table.actions("Linux64")
        for action in actions:
            action.execute(self.eups, 1, True)

    

__all__ = "TableTestCase1 TableTestCase2 EmptyTableTestCase".split()

if __name__ == "__main__":
    unittest.main()
