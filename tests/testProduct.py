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

from eups.product import Product

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
        self.assert_(self.prod.table is None)

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
        self.assert_(p.table is None)

    def testStackRoot(self):
        self.assert_(self.prod.stackRoot() is None)
        self.prod.db = os.path.join(self.prod.dir, "ups_db")
        self.assertEquals(self.prod.stackRoot(), self.prod.dir)

    def tearDown(self):
        if os.path.exists("test_product.pickle"):
            os.remove("test_product.pickle")

__all__ = "ProductTestCase".split()

if __name__ == "__main__":
    unittest.main()
