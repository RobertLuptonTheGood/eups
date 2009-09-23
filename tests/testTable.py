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

class TableTestCase(unittest.TestCase):
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



__all__ = "TableTestCase".split()

if __name__ == "__main__":
    unittest.main()
