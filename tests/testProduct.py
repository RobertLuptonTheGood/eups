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
        self.assert_(self.prod.db is None)
        self.assert_(self.prod._table is None)
        self.assert_(self.prod.tablefile is None)
        self.assert_(self.prod._prodStack is None)

        db = os.path.join(os.environ["PWD"], "ups_db")
        p = Product("eups", "1.0", dir=os.environ["PWD"], 
                    tags="stable mine".split(), db=db)
        self.assertEqual(p.db, db)
        self.assertEqual(len(p.tags), 2)
        self.assertIn("stable", p.tags)
        self.assertIn("mine", p.tags)

    def testPersist(self):
        fd = open("test_product.pickle", "wb")
        self.prod.persist(fd)
        fd.close()
        fd = open("test_product.pickle", "rb")
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
                       
        self.assertEquals(prod.dir, pdir)
        self.assertEquals(prod.db, self.dbpath)
        self.assert_(prod.ups_dir is None)
        self.assert_(prod.tablefile is None)
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # test cloning (we'll use this later)
        clone = prod.clone()
        self.assertEquals(clone.dir, pdir)
        self.assertEquals(clone.db, self.dbpath)
        self.assert_(clone.ups_dir is None)
        self.assert_(clone.tablefile is None)
        self.assertEquals(clone.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # turn to absolute paths
        prod.resolvePaths()
        self.assertEquals(prod.dir, pdir)
        self.assertEquals(prod.db, self.dbpath)
        self.assertEquals(prod.tablefile, 
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEquals(prod.ups_dir, os.path.join(pdir,"ups"))
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # turn to relative paths
        prod.canonicalizePaths()
        self.assertEquals(prod.dir, "Linux/newprod/2.0")
        self.assertEquals(prod.db, self.dbpath)
        self.assertEquals(prod.tablefile, pname+".table")
        self.assertEquals(prod.ups_dir, "ups")
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # round trip: turn back to absolute paths
        prod.resolvePaths()
        self.assertEquals(prod.dir, pdir)
        self.assertEquals(prod.db, self.dbpath)
        self.assertEquals(prod.tablefile, 
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEquals(prod.ups_dir, os.path.join(pdir,"ups"))
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # turn original to relative paths
        clone.canonicalizePaths()
        self.assertEquals(clone.dir, "Linux/newprod/2.0")
        self.assertEquals(clone.db, self.dbpath)
        self.assertEquals(clone.tablefile, pname+".table")
        self.assertEquals(clone.ups_dir, "ups")
        self.assertEquals(clone.tableFileName(), 
                          os.path.join(pdir,"ups",pname+".table"))

        # back to absolute paths
        clone.resolvePaths()
        self.assertEquals(clone.dir, pdir)
        self.assertEquals(clone.db, self.dbpath)
        self.assertEquals(clone.tablefile, 
                          os.path.join(pdir,"ups",pname+".table"))
        self.assertEquals(clone.ups_dir, os.path.join(pdir,"ups"))
        self.assertEquals(clone.tableFileName(), 
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

        self.assertEquals(prod.dir, pdir)
        self.assertEquals(prod.db, self.dbpath)
        self.assertEquals(prod.tablefile, 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assert_(prod.ups_dir is None)
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # test cloning (we'll use this later)
        clone = prod.clone()
        self.assertEquals(clone.dir, pdir)
        self.assertEquals(clone.db, self.dbpath)
        self.assertEquals(clone.tablefile, 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assert_(clone.ups_dir is None)
        self.assertEquals(clone.tableFileName(), 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # turn to absolute paths
        prod.resolvePaths()
        self.assertEquals(prod.dir, pdir)
        self.assertEquals(prod.db, self.dbpath)
        self.assert_(prod.ups_dir is None)
        self.assertEquals(prod.tablefile, 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        prod.canonicalizePaths()
        self.assertEquals(prod.dir, "Linux/newprod/2.0")
        self.assertEquals(prod.db, self.dbpath)
        self.assertEquals(prod.ups_dir, "$UPS_DB/newprod/Linux")
        self.assertEquals(prod.tablefile, "2.0.table")
        self.assertEquals(prod.tableFileName(), 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # turn original to relative paths
        clone.canonicalizePaths()
        self.assertEquals(clone.dir, "Linux/newprod/2.0")
        self.assertEquals(clone.db, self.dbpath)
        self.assertEquals(clone.ups_dir, "$UPS_DB/newprod/Linux")
        self.assertEquals(clone.tablefile, "2.0.table")
        self.assertEquals(clone.tableFileName(), 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))

        # back to absolute paths
        clone.resolvePaths()
        self.assertEquals(clone.dir, pdir)
        self.assertEquals(clone.db, self.dbpath)
        self.assertEquals(clone.ups_dir, 
                          os.path.join(self.dbpath,pname,"Linux"))
        self.assertEquals(clone.tablefile, 
                          os.path.join(self.dbpath,"newprod/Linux/2.0.table"))
        self.assertEquals(clone.tableFileName(), 
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
