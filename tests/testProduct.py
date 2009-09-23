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

class ProductTestCase(unittest.TestCase):
    """test the Product container class"""

    def setUp(self):
        self.prod = Product("eups", "1.0", dir=testEupsStack)

    def testToString(self):
        self.assertEqual(str(self.prod), "Product: eups 1.0")

    def testInit(self):
        self.assertEqual(self.prod.name, "eups")
        self.assertEqual(self.prod.version, "1.0")
        self.assertEqual(self.prod.dir, testEupsStack)
        self.assert_(self.prod.db is None)
        self.assert_(self.prod._table is None)
        self.assert_(self.prod.tablefile is None)
        self.assert_(self.prod._prodStack is None)

        db = os.path.join(os.environ["PWD"], "ups_db")
        p = Product("eups", "1.0", dir=os.environ["PWD"], 
                    tags="stable mine".split(), db=db)
        self.assertEqual(p.db, db)
        self.assertEqual(len(p.tags), 2)
        self.assert_("stable" in p.tags)
        self.assert_("mine" in p.tags)

    def testPersist(self):
        fd = file("test_product.pickle", "w")
        self.prod.persist(fd)
        fd.close()
        fd = file("test_product.pickle")
        p = Product.unpersist(fd)

        self.assertEqual(self.prod.name, p.name)
        self.assertEqual(self.prod.version, p.version)
        self.assertEqual(self.prod.dir, p.dir)
        self.assertEqual(self.prod.db, p.db)
        self.assert_(self.prod._table is None)
        self.assert_(self.prod.tablefile is None)

    def testStackRoot(self):
        self.assert_(self.prod.stackRoot() is None)
        self.prod.db = os.path.join(self.prod.dir, "ups_db")
        self.assertEquals(self.prod.stackRoot(), self.prod.dir)

    def testTableFileName(self):
        path = self.prod.tableFileName()
        self.assertEquals(path, os.path.join(testEupsStack,"ups","eups.table"))

        self.prod.tablefile = "none"
        self.assert_(self.prod.tableFileName() is None)

        self.prod.tablefile = "/tmp/eups.table"
        self.assertEquals(self.prod.tableFileName(), "/tmp/eups.table")

    def testTableFileName2(self):
        self.prod.name = None
        self.assert_(self.prod.tableFileName() is None)

    def testTableFileName3(self):
        self.prod.dir = None
        self.assert_(self.prod.tableFileName() is None)
        self.prod.dir = "none"
        self.assert_(self.prod.tableFileName() is None)

    def testGetTable(self):
        self.assertRaises(TableFileNotFound, self.prod.getTable)

    def tearDown(self):
        if os.path.exists("test_product.pickle"):
            os.remove("test_product.pickle")

__all__ = "ProductTestCase".split()

if __name__ == "__main__":
    unittest.main()
