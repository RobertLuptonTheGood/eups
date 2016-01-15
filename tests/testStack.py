#!/usr/bin/env python
"""
Tests for eups.stack
"""

import os
import unittest
import time
import testCommon
from testCommon import testEupsStack
from eups.Product import ProductNotFound, Product

from eups.stack import ProductFamily

class ProductFamilyTestCase(unittest.TestCase):

    def setUp(self):
        self.fam = ProductFamily("magnum")

    def testNotFound(self):
        self.assertRaises(ProductNotFound, self.fam.getProduct, "4.0")

    def testAddVersion(self):
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1")
        self.assertEquals(len(self.fam.getVersions()), 1)
        self.assert_(not self.fam.hasVersion("1.0"))
        self.assert_(self.fam.hasVersion("3.1"))
        self.fam.addVersion("3.2", "/opt/LInux/magnum/3.2")
        self.assertEquals(len(self.fam.getVersions()), 2)
        self.assert_(self.fam.hasVersion("3.1"))
        self.assert_(not self.fam.removeVersion("1.0"))
        self.assert_(self.fam.removeVersion("3.1"))
        self.assert_(not self.fam.hasVersion("3.1"))
        self.assert_(self.fam.removeVersion("3.2"))

    def testGetProduct(self):
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1")
        p = self.fam.getProduct("3.1")
        self.assertEqual(p.name, "magnum")
        self.assertEqual(p.version, "3.1")
        self.assertEqual(p.dir, "/opt/LInux/magnum/3.1")

    def testAssignTag(self):
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1")
        self.fam.addVersion("3.2", "/opt/LInux/magnum/3.2")
        self.assertEquals(len(self.fam.getTags()), 0)
        tag = "stable"
        self.assert_(not self.fam.isTagAssigned(tag))
        self.fam.assignTag(tag, "3.1")
        self.assertEquals(len(self.fam.getTags()), 1)
        self.assert_(self.fam.isTagAssigned(tag))
        self.fam.assignTag("beta", "3.2")
        self.fam.assignTag("current", "3.1")
        self.assertEquals(len(self.fam.getTags()), 3)
        self.assert_(self.fam.isTagAssigned("beta"))
        self.assert_(self.fam.isTagAssigned("current"))
        p = self.fam.getProduct("3.1")
        self.assertEquals(len(p.tags), 2)
        self.assert_(tag in p.tags)
        self.assert_("current" in p.tags)
        p = self.fam.getTaggedProduct("beta")
        self.assertEquals(p.version, "3.2")
        self.assertEquals(len(p.tags), 1)
        self.assert_("beta" in p.tags)
        p = self.fam.getTaggedProduct(tag)
        self.assertEquals(p.version, "3.1")
        self.assertEquals(len(p.tags), 2)
        self.assert_(tag in p.tags)
        self.assert_("current" in p.tags)

        self.assert_(not self.fam.unassignTag("gurn"))
        self.assert_(self.fam.unassignTag("beta"))
        self.assert_(not self.fam.isTagAssigned("beta"))
        self.assert_(self.fam.isTagAssigned("current"))

    def testExport(self):
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1")
        self.fam.addVersion("3.2", "/opt/LInux/magnum/3.2")
        self.fam.assignTag("stable", "3.1")
        self.fam.assignTag("beta", "3.2")
        self.fam.assignTag("current", "3.1")

        prods = self.fam.export(flavor="Linux")
        self.assertEquals(len(prods.keys()), 2)
        p = prods["3.1"]
        self.assertEquals(p.name, "magnum")
        self.assertEquals(p.flavor, "Linux")
        self.assert_(p.db is None)
        self.assertEquals(len(p.tags), 2)
        self.assert_("current" in p.tags)
        p.name = "helpful"

        fam = ProductFamily("helpful")
        fam.import_(prods)
        self.assertEquals(len(fam.getVersions()), 1)
        self.assert_(fam.hasVersion("3.1"))

    def testLoadTable(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1", tablefile)
        prod = self.fam.getProduct("3.1")
        self.assert_(prod.tablefile is not None)
        self.assert_(os.path.exists(prod.tablefile))
        self.assert_(prod._table is None)
        self.fam.loadTableFor("3.1")
        prod = self.fam.getProduct("3.1")
        self.assert_(prod._table is not None)

    def testLoadTables(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        self.fam.addVersion("3.1", "/opt/LInux/magnum/3.1", tablefile)
        prod = self.fam.getProduct("3.1")
        self.assert_(prod.tablefile is not None)
        self.assert_(os.path.exists(prod.tablefile))
        self.assert_(prod._table is None)
        self.fam.loadTableFor("3.1")

        self.fam.loadTables()
        prod = self.fam.getProduct("3.1")
        self.assert_(prod._table is not None)
        
        

from eups.stack import ProductStack
from eups import UnderSpecifiedProduct

class ProductStackTestCase(unittest.TestCase):

    def setUp(self):
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.stack = ProductStack(self.dbpath, autosave=False)
        self.stack.addProduct(Product("fw", "1.2", "Darwin", 
                                      "/opt/sw/Darwin/fw/1.2", "none"))

    def testMisc(self):
        self.assertEquals(ProductStack.persistFilename("Linux"),
                          "Linux.pickleDB1_3_0")
        self.assertEquals(self.stack.getDbPath(), 
                          os.path.join(testEupsStack, "ups_db"))

    def testGetProductNames(self):
        prods = self.stack.getProductNames()
        self.assertEquals(len(prods), 1)
        self.assertEquals(prods[0], 'fw')

        self.stack.addProduct(Product("afw", "1.2", "Linux", 
                                      "/opt/sw/Linux/afw/1.2", "none"))
        prods = self.stack.getProductNames()
        self.assertEquals(len(prods), 2)
        expected = "fw afw".split()
        for prod in expected:
            self.assert_(prod in prods)
        prods = self.stack.getProductNames("Linux")
        self.assertEquals(len(prods), 1)
        self.assertEquals(prods[0], 'afw')

        self.stack.addProduct(Product("fw", "1.2", "Linux", 
                                      "/opt/sw/Linux/fw/1.2", "none"))
        prods = self.stack.getProductNames()
        self.assertEquals(len(prods), 2)
        for prod in expected:
            self.assert_(prod in prods)

    def testGetVersions(self):
        vers = self.stack.getVersions("afw")
        self.assertEquals(len(vers), 0)

        vers = self.stack.getVersions("fw")
        self.assertEquals(len(vers), 1)
        self.assertEquals(vers[0], '1.2')

        self.stack.addProduct(Product("fw", "1.3", "Linux", 
                                      "/opt/sw/Linux/fw/1.3", "none"))
        vers = self.stack.getVersions("fw")
        self.assertEquals(len(vers), 2)
        expected = "1.2 1.3".split()
        for ver in expected:
            self.assert_(ver in vers)

        vers = self.stack.getVersions("fw", "Linux")
        self.assertEquals(len(vers), 1)
        self.assertEquals(vers[0], '1.3')

        self.stack.addProduct(Product("fw", "1.2", "Linux", 
                                      "/opt/sw/Linux/fw/1.2", "none"))
        vers = self.stack.getVersions("fw")
        self.assertEquals(len(vers), 2)
        for ver in expected:
            self.assert_(ver in vers)
        vers = self.stack.getVersions("fw", "Linux")
        self.assertEquals(len(vers), 2)
        for ver in expected:
            self.assert_(ver in vers)

    def testAutoSave(self):
        self.assert_(self.stack.saveNeeded())

        cache = os.path.join(os.environ["PWD"],
                             ProductStack.persistFilename("Darwin"))
        if os.path.exists(cache):  os.remove(cache)

        stack = ProductStack(os.path.join(testEupsStack, "ups_db"), 
                             os.environ["PWD"], autosave=True)
        self.assert_(not stack.saveNeeded())
        stack.addProduct(Product("fw", "1.2", "Darwin", 
                                 "/opt/sw/Darwin/fw/1.2", "none"))
        self.assert_(not stack.saveNeeded())
        self.assert_(os.path.exists(cache))
        if os.path.exists(cache):  os.remove(cache)

    def testHasProduct(self):
        self.assert_(self.stack.hasProduct("fw"))
        self.assert_(not self.stack.hasProduct("afw"))
        self.assert_(self.stack.hasProduct("fw", "Darwin"))
        self.assert_(not self.stack.hasProduct("fw", "Linux"))
        self.assert_(self.stack.hasProduct("fw", "Darwin", "1.2"))
        self.assert_(not self.stack.hasProduct("fw", "Darwin", "1.3"))
        self.assert_(not self.stack.hasProduct("afw", "Darwin", "1.2"))
        self.assert_(not self.stack.hasProduct("fw", "Linux", "1.2"))
        self.assert_(self.stack.hasProduct("fw", version="1.2"))
        self.assert_(not self.stack.hasProduct("fw", version="1.3"))

    def testAddProduct(self):
        self.assertRaises(TypeError, 
                          self.stack.addProduct, "fw", "1.2", "Linux")
        self.assertRaises(TypeError, self.stack.addProduct, "fw")
        prod = Product("fw", "1.2")
        self.assertRaises(UnderSpecifiedProduct, self.stack.addProduct, prod)

        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", "none")
        self.stack.addProduct(prod)
        self.assert_(self.stack.hasProduct("afw"))
        p = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assertEquals(p.name, prod.name)
        self.assertEquals(p.version, prod.version)
        self.assertEquals(p.flavor, prod.flavor)
        self.assertEquals(p.dir, prod.dir)
        self.assertEquals(p.tablefile, prod.tablefile)
        self.assertEquals(p.db, os.path.join(testEupsStack, "ups_db"))
        self.assertEquals(len(p.tags), 0)

        self.assertRaises(ProductNotFound, 
                          self.stack.getProduct, "afw", "1.2", "Linux")
        self.assertRaises(ProductNotFound, 
                          self.stack.getProduct, "afw", "1.3", "Darwin")

        self.stack.removeProduct("afw", "Darwin", "1.2")
        self.assert_(not self.stack.hasProduct("afw"))
        self.assert_(not self.stack.removeProduct("afw", "Darwin", "1.2"))

    def testGetFlavors(self):
        flavors = self.stack.getFlavors()
        self.assertEquals(len(flavors), 1)
        self.assertEquals(flavors[0], "Darwin")
        prod = Product("afw", "1.2", "Linux", "/opt/sw/Linux/afw/1.2", "none")
        self.stack.addProduct(prod)
        flavors = self.stack.getFlavors()
        self.assertEquals(len(flavors), 2)
        expected = "Darwin Linux".split()
        for flav in expected:
            self.assert_(flav in flavors)

    def testAddFlavor(self):
        flavors = self.stack.getFlavors()
        self.assertEquals(len(flavors), 1)
        self.assertEquals(flavors[0], "Darwin")
        self.stack.addFlavor("Darwin")

        flavors = self.stack.getFlavors()
        self.assertEquals(len(flavors), 1)
        self.assertEquals(flavors[0], "Darwin")
        self.assert_(self.stack.lookup["Darwin"])

        self.stack.addFlavor("Linux")
        flavors = self.stack.getFlavors()
        self.assertEquals(len(flavors), 2)
        expected = "Darwin Linux".split()
        for flav in expected:
            self.assert_(flav in flavors)
        self.assertEquals(len(self.stack.getProductNames("Linux")), 0)
        self.assert_(not self.stack.lookup["Linux"])

    def testTags(self):
        self.assertEquals(len(self.stack.getTags()), 0)

        prod = Product("afw", "1.2", "Linux", "/opt/sw/Linux/afw/1.2", "none")
        prod.tags = ["current", "beta"]
        self.stack.addProduct(prod)
        self.assertEquals(len(self.stack.getTags()), 2)
        prod.version = "1.3"
        prod.tags = []
        self.stack.addProduct(prod)
        tags = self.stack.getTags()
        self.assertEquals(len(tags), 2)
        self.assertEquals(tags[0], "beta")
        self.assertEquals(tags[1], "current")
        prod = self.stack.getTaggedProduct("afw", "Linux", "stable")
        self.assert_(prod is None)
        prod = self.stack.getTaggedProduct("afw", "Linux", "beta")
        self.assertEqual(prod.version, "1.2")
        self.assertEqual(prod.flavor, "Linux")
        self.assertEqual(prod.db, self.dbpath)

        self.assertRaises(ProductNotFound, 
                          self.stack.assignTag, "gurn", "goober", "2")
        self.stack.assignTag("beta", "afw", "1.3")
        tags = self.stack.getTags()
        self.assertEquals(len(tags), 2)
        self.assertEquals(tags[0], "beta")
        self.assertEquals(tags[1], "current")
        prod = self.stack.getTaggedProduct("afw", "Linux", "beta")
        self.assertEqual(prod.version, "1.3")
        self.assertEqual(prod.flavor, "Linux")
        self.assertEqual(prod.db, self.dbpath)

        self.assert_(not self.stack.unassignTag("gurn", "afw", "Linux"))
        self.assert_(self.stack.unassignTag("beta", "afw"))
        tags = self.stack.getTags()
        self.assertEquals(len(tags), 1)
        self.assertEquals(tags[0], "current")

    def testSaveEmptyFlavor(self):
        self.stack.clearCache("Linux")
        cache = os.path.join(self.dbpath, 
                             ProductStack.persistFilename("Linux"))
        self.assert_(not os.path.exists(cache))

        try: 
            self.stack.save("Linux")
            self.assert_(os.path.exists(cache))
            self.stack.reload("Linux")
            flavors = self.stack.getFlavors()
            self.assertEquals(len(flavors), 2)
            expected = "Darwin Linux".split()
            for flav in expected:
                self.assert_(flav in flavors)
            self.assertEquals(len(self.stack.getProductNames("Linux")), 0)

        finally:
            if os.path.exists(cache):
                os.remove(cache)

    def testSave(self):
        self.assert_(self.stack.saveNeeded())

        self.stack.clearCache("Linux Linux64 Darwin DarwinX86 generic".split())
        self.assertEquals(len(ProductStack.findCachedFlavors(self.dbpath)),0)

        cache = os.path.join(self.dbpath, 
                             ProductStack.persistFilename("Darwin"))
        self.assert_(not os.path.exists(cache))

        self.stack.save()
        self.assert_(not self.stack.saveNeeded())
        self.assert_(os.path.exists(cache))

        saved = ProductStack.findCachedFlavors(self.dbpath)
        self.assertEquals(len(saved), 1)
        self.assertEquals(saved[0], "Darwin")

        self.stack.reload("Darwin")
        self.assertEquals(len(self.stack.getProductNames("Darwin")), 1)
        p = self.stack.getProduct("fw", "1.2", "Darwin")
        self.assertEquals(p.name, "fw")
        self.assertEquals(p.version, "1.2")
        self.assertEquals(p.flavor, "Darwin")
        self.assertEquals(p.dir, "/opt/sw/Darwin/fw/1.2")
        self.assertEquals(p.tablefile, "none")
        self.assertEquals(p.db, self.dbpath)
        

        self.stack.clearCache()
        self.assertEquals(len(ProductStack.findCachedFlavors(self.dbpath)),0)
        self.assert_(not os.path.exists(cache))

    def testLoadTable(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", 
                       tablefile)
        self.stack.addProduct(prod)

        self.stack.loadTableFor(prod.name, prod.version, prod.flavor)
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is not None)

    def testLoadTables(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", 
                       tablefile)
        self.stack.addProduct(prod)

        self.stack.loadTables()
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is not None)

    def testLoadTablesForFlavor(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", 
                       tablefile)
        self.stack.addProduct(prod)

        self.stack.loadTables(flavors="Linux")
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is None)

        self.stack.loadTables(flavors="Darwin")
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is not None)

    def testLoadTablesForProd(self):
        tablefile = os.path.join(testEupsStack,"mwi.table")
        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", 
                       tablefile)
        self.stack.addProduct(prod)

        self.stack.loadTables("newprod")
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is None)

        self.stack.loadTables("afw")
        prod = self.stack.getProduct("afw", "1.2", "Darwin")
        self.assert_(prod._table is not None)



from eups.stack import CacheOutOfSync

class CacheTestCase(unittest.TestCase):

    def setUp(self):
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.cache = os.path.join(self.dbpath, 
                                  ProductStack.persistFilename("Linux"))
        if os.path.exists(self.cache):
            os.remove(self.cache)

    def tearDown(self):
        if os.path.exists(self.cache):
            os.remove(self.cache)

    def testRegen(self):
        ps = ProductStack.fromCache(self.dbpath, "Linux", autosave=True, 
                                    updateCache=True, verbose=False)
        self.assert_(not ps.hasProduct("afw"))
        prod = Product("afw", "1.2", "Darwin", "/opt/sw/Darwin/afw/1.2", "none")
        ps.addProduct(prod)
        ps.reload("Linux")
        self.assert_(ps.hasProduct("afw"))
        del ps
        ps = ProductStack.fromCache(self.dbpath, "Linux", autosave=False, 
                                    updateCache=True, verbose=False)
        self.assert_(not ps.hasProduct("afw"))

    def testDetectOutOfSync(self):
        ps1 = ProductStack.fromCache(self.dbpath, "Linux", autosave=False, 
                                     updateCache=True, verbose=1)
        ps2 = ProductStack.fromCache(self.dbpath, "Linux", autosave=False, 
                                     updateCache=True, verbose=1)
        time.sleep(1)
        ps1.addProduct(Product("fw", "1.2", "Linux", 
                               "/opt/sw/Darwin/fw/1.2", "none"))
        self.assert_(ps1.cacheIsInSync())
        ps1.save()
        self.assert_(ps1.cacheIsInSync())

        self.assert_(not ps2.cacheIsInSync())
        ps2.addProduct(Product("fw", "1.2", "Linux", 
                               "/opt/sw/Darwin/fw/1.2", "none"))
        self.assertRaises(CacheOutOfSync, ps2.save)
        
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        CacheTestCase,
        ProductFamilyTestCase,
        ProductStackTestCase
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
