#!/usr/bin/env python
"""
Tests for eups.product
"""

import os
import unittest

import testCommon
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
        self.assertIsNone(self.prod.db)
        self.assertIsNone(self.prod._table)
        self.assertIsNone(self.prod.tablefile)
        self.assertIsNone(self.prod._prodStack)

        db = os.path.join(os.environ["PWD"], "ups_db")
        p = Product("eups", "1.0", dir=os.environ["PWD"],
                    tags="stable mine".split(), db=db)
        self.assertEqual(p.db, db)
        self.assertEqual(len(p.tags), 2)
        self.assertIn("stable", p.tags)
        self.assertIn("mine", p.tags)

    def testStackRoot(self):
        self.assertIsNone(self.prod.stackRoot())
        self.prod.db = os.path.join(self.prod.dir, "ups_db")
        self.assertEqual(self.prod.stackRoot(), self.prod.dir)

    def testTableFileName(self):
        path = self.prod.tableFileName()
        self.assertEqual(path, os.path.join(testEupsStack,"ups","eups.table"))

        self.prod.tablefile = "none"
        self.assertIsNone(self.prod.tableFileName())

        self.prod.tablefile = "/tmp/eups.table"
        self.assertEqual(self.prod.tableFileName(), "/tmp/eups.table")

    def testTableFileName2(self):
        self.prod.name = None
        self.assertIsNone(self.prod.tableFileName())

    def testTableFileName3(self):
        self.prod.dir = None
        self.assertIsNone(self.prod.tableFileName())
        self.prod.dir = "none"
        self.assertIsNone(self.prod.tableFileName())

    def testGetTable(self):
        self.assertRaises(TableFileNotFound, self.prod.getTable)

    def tearDown(self):
        if os.path.exists("test_product.pickle"):
            os.remove("test_product.pickle")

class ProductTransformationTestCase(unittest.TestCase):

    def setUp(self):
        self.eupsPathDir = testEupsStack
        self.dbpath = os.path.join(self.eupsPathDir, "ups_db")

    def tearDown(self):
        pass

    def testProd1(self):
        pname = "newprod"
        pver = "2.0"
        pdir = os.path.join(self.eupsPathDir,"Linux",pname,pver)
        prod = Product("newprod", "2.0", "Linux", pdir, db=self.dbpath)

        self.assertEqual(prod.dir, pdir)
        self.assertEqual(prod.db, self.dbpath)
        self.assertIsNone(prod.ups_dir)
        self.assertIsNone(prod.tablefile)
        self.assertEqual(prod.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # test cloning (we'll use this later)
        clone = prod.clone()
        self.assertEqual(clone.dir, pdir)
        self.assertEqual(clone.db, self.dbpath)
        self.assertIsNone(clone.ups_dir)
        self.assertIsNone(clone.tablefile)
        self.assertEqual(clone.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # turn to absolute paths
        prod.resolvePaths()
        self.assertEqual(prod.dir, pdir)
        self.assertEqual(prod.db, self.dbpath)
        self.assertEqual(prod.tablefile,
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEqual(prod.ups_dir, os.path.join(pdir,"ups"))
        self.assertEqual(prod.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # turn to relative paths
        prod.canonicalizePaths()
        self.assertEqual(prod.dir, "Linux/newprod/2.0")
        self.assertEqual(prod.db, self.dbpath)
        self.assertEqual(prod.tablefile, pname+".table")
        self.assertEqual(prod.ups_dir, "ups")
        self.assertEqual(prod.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # round trip: turn back to absolute paths
        prod.resolvePaths()
        self.assertEqual(prod.dir, pdir)
        self.assertEqual(prod.db, self.dbpath)
        self.assertEqual(prod.tablefile,
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEqual(prod.ups_dir, os.path.join(pdir,"ups"))
        self.assertEqual(prod.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # turn original to relative paths
        clone.canonicalizePaths()
        self.assertEqual(clone.dir, "Linux/newprod/2.0")
        self.assertEqual(clone.db, self.dbpath)
        self.assertEqual(clone.tablefile, pname+".table")
        self.assertEqual(clone.ups_dir, "ups")
        self.assertEqual(clone.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

        # back to absolute paths
        clone.resolvePaths()
        self.assertEqual(clone.dir, pdir)
        self.assertEqual(clone.db, self.dbpath)
        self.assertEqual(clone.tablefile,
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEqual(clone.ups_dir, os.path.join(pdir,"ups"))
        self.assertEqual(clone.tableFileName(),
                          os.path.join(pdir,"ups",pname+".table"))

    def testProd2(self):
        """
        Test $UPS_DB transformations
        """
        pname = "newprod"
        pver = "2.0"
        pdir = os.path.join(self.eupsPathDir,"Linux",pname,pver)
        prod = Product("newprod", "2.0", "Linux", pdir, db=self.dbpath,
                       table=os.path.join(self.dbpath,pname,'Linux',
                                          pver+".table"))

        self.assertEqual(prod.dir, pdir)
        self.assertEqual(prod.db, self.dbpath)
        self.assertEqual(prod.tablefile,
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertIsNone(prod.ups_dir)
        self.assertEqual(prod.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # test cloning (we'll use this later)
        clone = prod.clone()
        self.assertEqual(clone.dir, pdir)
        self.assertEqual(clone.db, self.dbpath)
        self.assertEqual(clone.tablefile,
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertIsNone(clone.ups_dir)
        self.assertEqual(clone.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # turn to absolute paths
        prod.resolvePaths()
        self.assertEqual(prod.dir, pdir)
        self.assertEqual(prod.db, self.dbpath)
        self.assertIsNone(prod.ups_dir)
        self.assertEqual(prod.tablefile,
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertEqual(prod.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        prod.canonicalizePaths()
        self.assertEqual(prod.dir, "Linux/newprod/2.0")
        self.assertEqual(prod.db, self.dbpath)
        self.assertEqual(prod.ups_dir, "$UPS_DB/newprod/Linux")
        self.assertEqual(prod.tablefile, "2.0.table")
        self.assertEqual(prod.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # turn original to relative paths
        clone.canonicalizePaths()
        self.assertEqual(clone.dir, "Linux/newprod/2.0")
        self.assertEqual(clone.db, self.dbpath)
        self.assertEqual(clone.ups_dir, "$UPS_DB/newprod/Linux")
        self.assertEqual(clone.tablefile, "2.0.table")
        self.assertEqual(clone.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # back to absolute paths
        clone.resolvePaths()
        self.assertEqual(clone.dir, pdir)
        self.assertEqual(clone.db, self.dbpath)
        self.assertEqual(clone.ups_dir,
                          os.path.join(self.dbpath,pname,"Linux"))
        self.assertEqual(clone.tablefile,
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertEqual(clone.tableFileName(),
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite((ProductTestCase, ProductTransformationTestCase), makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
