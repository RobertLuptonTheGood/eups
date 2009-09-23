#!/usr/bin/env python
"""
Tests for eups.db
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import shutil
import unittest
import time
from testCommon import testEupsStack

from eups import ProductNotFound, Product
from eups.db import VersionFile

class VersionFileTestCase(unittest.TestCase):

    def setUp(self):
        self.vf = VersionFile(os.path.join(testEupsStack, "fw.version"))

    def testParsing(self):
        self.assertEquals(self.vf.name, "fw")
        self.assertEquals(self.vf.version, "1.2")
        flavors = self.vf.getFlavors()
        self.assertEquals(len(flavors), 2)
        self.assert_("DarwinX86" in flavors)
        self.assert_("Darwin" in flavors)

        flavor = self.vf.info["DarwinX86"]
        self.assertEquals(flavor['declarer'], 'rhl')
        self.assertEquals(flavor['modifier'], 'rhl')
        self.assertEquals(flavor['productDir'], 'DarwinX86/fw/1.2')
        self.assertEquals(flavor['modified'], 'Tue Oct  9 22:05:03 2007')
        self.assertEquals(flavor['declared'], 'Tue Oct  9 22:05:03 2007')
        self.assertEquals(flavor['ups_dir'], '$PROD_DIR/ups')
        self.assertEquals(flavor['table_file'], 'fw.table')

        flavor = self.vf.info["Darwin"]
        self.assertEquals(flavor['declarer'], 'rhl')
        self.assertEquals(flavor['modifier'], 'rhl')
        self.assertEquals(flavor['productDir'], 'DarwinX86/fw/1.2')
        self.assertEquals(flavor['modified'], 'Tue Oct  9 22:05:03 2005')
        self.assertEquals(flavor['declared'], 'Tue Oct  9 22:05:03 2005')
        self.assertEquals(flavor['ups_dir'], '$PROD_DIR/ups')
        self.assertEquals(flavor['table_file'], 'fw.table')

        self.vf = VersionFile(os.path.join(testEupsStack, "fw.version"),
                              "afw", "3.2", verbosity=-1)
        self.assertEquals(self.vf.name, "afw")
        self.assertEquals(self.vf.version, "3.2")
        flavors = self.vf.getFlavors()
        self.assertEquals(len(flavors), 2)

    def testAddFlavor(self):
        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2", 
                          "/opt/sw/Linux/fw/1.2/ups/fw.table")
        flavors = self.vf.getFlavors()
        self.assertEquals(len(flavors), 3)
        self.assert_("Linux:rhel" in flavors)
        info = self.vf.info["Linux:rhel"]
        self.assertEquals(info["table_file"], "fw.table")
        self.assertEquals(info["ups_dir"], "ups")
        self.assertEquals(info["productDir"], "/opt/sw/Linux/fw/1.2")
        self.assert_(info.has_key("declarer"))
        self.assert_(info.has_key("declared"))
        self.assert_(not info.has_key("modifier"))
        declared = info["declared"]
        declarer = info["declarer"]

        self.vf.addFlavor("Linux:rhel", upsdir="ups")
        flavors = self.vf.getFlavors()
        self.assertEquals(len(flavors), 3)
        self.assert_("Linux:rhel" in flavors)
        info = self.vf.info["Linux:rhel"]
        self.assertEquals(info["table_file"], "fw.table")
        self.assertEquals(info["ups_dir"], "ups")
        self.assertEquals(info["productDir"], "/opt/sw/Linux/fw/1.2")
        self.assertEquals(info["declarer"], declarer)
        self.assertEquals(info["declared"], declared)
        self.assertEquals(info["modifier"], declarer)
        self.assert_(info.has_key("modified"))

        self.vf.removeFlavor("Linux:rhel")
        flavors = self.vf.getFlavors()
        self.assertEquals(len(flavors), 2)
        self.vf.removeFlavor(flavors)
        self.assertEquals(len(self.vf.getFlavors()), 0)
        self.assert_(self.vf.isEmpty())

    def testMakeProduct(self):
        prod = self.vf.makeProduct("Darwin")
        self.assertEquals(prod.name, "fw")
        self.assertEquals(prod.version, "1.2")
        self.assertEquals(prod.dir, "DarwinX86/fw/1.2")
        self.assertEquals(prod.flavor, "Darwin")
        self.assertEquals(prod.tablefile, "DarwinX86/fw/1.2/ups/fw.table")
        self.assertEquals(len(prod.tags), 0)
        self.assert_(prod.db is None)

        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2", 
                          "/opt/sw/Linux/fw/1.2/ups/fw.table", "ups")
        prod = self.vf.makeProduct("Linux:rhel")
        self.assertEquals(prod.name, "fw")
        self.assertEquals(prod.version, "1.2")
        self.assertEquals(prod.dir, "/opt/sw/Linux/fw/1.2")
        self.assertEquals(prod.flavor, "Linux:rhel")
        self.assertEquals(prod.tablefile, "/opt/sw/Linux/fw/1.2/ups/fw.table")
        self.assertEquals(len(prod.tags), 0)
        self.assert_(prod.db is None)

        self.assertRaises(ProductNotFound, self.vf.makeProduct, "goober")

        prod = self.vf.makeProducts()
        self.assertEquals(len(prod), 3)
        for p in prod:
            self.assert_(isinstance(p, Product))

    def testWrite(self):
        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2", 
                          "/opt/sw/Linux/fw/1.2/ups/fw.table", "ups")

        self.assertEquals(len(self.vf.getFlavors()), 3)
        file=os.path.join(testEupsStack, "tst.version")
        self.vf.write(file=file)

        vf = VersionFile(file)
        self.assertEquals(vf.name, "fw")
        self.assertEquals(vf.version, "1.2")
        flavors = vf.getFlavors()
        self.assertEquals(len(flavors), 3)
        self.assert_("DarwinX86" in flavors)
        self.assert_("Darwin" in flavors)
        self.assert_("Linux:rhel" in flavors)


from eups.db import ChainFile

class ChainFileTestCase(unittest.TestCase):

    def setUp(self):
        self.cf = ChainFile(os.path.join(testEupsStack, "fw.current"))

    def testParsing(self):
        self.assertEquals(self.cf.name, "fw")
        self.assertEquals(self.cf.tag, "current")
        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 1)
        self.assert_("DarwinX86" in flavors)

        flavor = self.cf.info["DarwinX86"]
        self.assertEquals(flavor['declarer'], 'rhl')
        self.assertEquals(flavor['modifier'], 'rhl')
        self.assertEquals(flavor['version'], 'svn3941')
        self.assertEquals(flavor['modified'], 'Thu Jan 24 23:43:35 2008')
        self.assertEquals(flavor['declared'], 'Thu Jan 24 23:43:35 2008')

        self.assertEquals(self.cf.getVersion("DarwinX86"), "svn3941")

        self.cf = ChainFile(os.path.join(testEupsStack, "fw.current"),
                            "afw", "stable", verbosity=-1)
        self.assertEquals(self.cf.name, "afw")
        self.assertEquals(self.cf.tag, "stable")
        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 1)

    def testSetVersion(self):
        self.cf.setVersion("2.0", "Linux")

        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 2)
        self.assert_("Linux" in flavors)

        flavor = self.cf.info["Linux"]
        self.assertEquals(flavor['version'], '2.0')
        self.assert_(bool(flavor['declarer']))
        self.assert_(bool(flavor['declared']))
        self.assert_(not flavor.has_key('modifier'))
        self.assert_(not flavor.has_key('modified'))
        who = flavor['declarer']
    
        self.cf.setVersion("2.1", "Linux64")

        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 3)
        self.assert_("Linux64" in flavors)

        flavor = self.cf.info["Linux64"]
        self.assertEquals(flavor['version'], '2.1')
        self.assertEquals(flavor['declarer'], who)
        self.assert_(bool(flavor['declared']))
        self.assert_(not flavor.has_key('modifier'))
        self.assert_(not flavor.has_key('modified'))

        # an update to an existing flavor
        self.cf.setVersion("2.1", "DarwinX86")

        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 3)
        self.assert_("DarwinX86" in flavors)

        flavor = self.cf.info["DarwinX86"]
        self.assertEquals(flavor['version'], '2.1')
        self.assertEquals(flavor['declarer'], 'rhl')
        self.assertEquals(flavor['declared'], 'Thu Jan 24 23:43:35 2008')
        self.assertEquals(flavor['modifier'], who)
        self.assert_(bool(flavor['modified']))

        self.cf.removeVersion("Linux64")
        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 2)
        self.assert_("DarwinX86" in flavors)
        self.assert_("Linux" in flavors)
        
        self.cf.removeVersion()
        flavors = self.cf.getFlavors()
        self.assertEquals(len(flavors), 0)
        
        self.assert_(self.cf.hasNoAssignments())

    def testWrite(self):
        self.cf.setVersion("2.0", "Linux:rhel")
        self.assertEquals(len(self.cf.getFlavors()), 2)

        file=os.path.join(testEupsStack, "tst.current")
        self.cf.write(file)

        cf = ChainFile(file)
        self.assertEquals(cf.name, "fw")
        self.assertEquals(cf.tag, "current")
        flavors = cf.getFlavors()
        self.assertEquals(len(flavors), 2)
        self.assert_("DarwinX86" in flavors)

        flavor = cf.info["DarwinX86"]
        self.assertEquals(flavor['declarer'], 'rhl')
        self.assertEquals(flavor['modifier'], 'rhl')
        self.assertEquals(flavor['version'], 'svn3941')
        self.assertEquals(flavor['modified'], 'Thu Jan 24 23:43:35 2008')
        self.assertEquals(flavor['declared'], 'Thu Jan 24 23:43:35 2008')

        self.assert_("Linux:rhel" in flavors)


from eups.db import Database

class DatabaseTestCase(unittest.TestCase):

    def setUp(self):
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.db = Database(self.dbpath)

        self.pycur = os.path.join(self.dbpath,"python","current.chain")
        if os.path.isfile(self.pycur+".bak"):
            os.rename(self.pycur+".bak", self.pycur)

    def testFindProductNames(self):
        prods = self.db.findProductNames()
        self.assertEquals(len(prods), 6)
        expected = "cfitsio tcltk eigen mpich2 python doxygen".split()
        for p in expected:
            self.assert_(p in prods)

    def testFindVersions(self):
        vers = self.db.findVersions("goober")
        self.assertEquals(len(vers), 0)

        vers = self.db.findVersions("doxygen")
        self.assertEquals(len(vers), 2)
        expected = "1.5.7.1 1.5.9".split()
        for v in expected:
            self.assert_(v in vers)

    def testFindFlavors(self):
        flavs = self.db.findFlavors("doxygen")
        self.assertEquals(len(flavs), 2)
        expected = "Linux Linux64".split()
        for f in expected:
            self.assert_(f in flavs)

        flavs = self.db.findFlavors("doxygen", "1.5.9")
        self.assertEquals(len(flavs), 1)
        expected = "Linux64".split()
        for f in expected:
            self.assert_(f in flavs)

        flavs = self.db.findFlavors("doxygen", "1.5.10")
        self.assertEquals(len(flavs), 0)

    def testFindTags(self):
        self.assertRaises(ProductNotFound, self.db.findTags, 
                          "goober", "1.5.9", "Linux64")

        tags = self.db.findTags("doxygen", "1.5.10", "Linux64")
        self.assertEquals(len(tags), 0)

        tags = self.db.findTags("doxygen", "1.5.9", "Linux64")
        self.assertEquals(len(tags), 0)

        tags = self.db.findTags("doxygen", "1.5.7.1", "Linux")
        self.assertEquals(len(tags), 1)
        self.assertEquals(tags[0], "current")

    def testFindProduct(self):
        prod = self.db.findProduct("doxygen", "1.5.9", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("doxygen", "1.5.10", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("goober", "1.5.10", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("doxygen", "1.5.9", "Linux64")
        self.assert_(prod is not None)
        self.assertEquals(prod.name, "doxygen")
        self.assertEquals(prod.version, "1.5.9")
        self.assertEquals(prod.flavor, "Linux64")
        self.assertEquals(prod.db, os.path.join(testEupsStack, "ups_db"))
        self.assertEquals(prod.dir, 
                "/lsst/DC3/stacks/gcc433/04jun/Linux64/external/doxygen/1.5.9")
        self.assertEquals(prod.tablefile, "/lsst/DC3/stacks/gcc433/04jun/Linux64/external/doxygen/1.5.9/ups/doxygen.table")
        self.assertEquals(len(prod.tags), 0)

        prod = self.db.findProduct("doxygen", "1.5.7.1", "Linux")
        self.assert_(prod is not None)
        self.assertEquals(prod.name, "doxygen")
        self.assertEquals(prod.version, "1.5.7.1")
        self.assertEquals(prod.flavor, "Linux")
        self.assertEquals(prod.db, os.path.join(testEupsStack, "ups_db"))
        self.assertEquals(prod.dir, 
                "/home/rplante/wrk/NCSA/LSST/devlp/stacks/21mar/Linux/external/doxygen/1.5.7.1")
        self.assertEquals(prod.tablefile, "/home/rplante/wrk/NCSA/LSST/devlp/stacks/21mar/Linux/external/doxygen/1.5.7.1/ups/doxygen.table")
        self.assertEquals(len(prod.tags), 1)
        self.assertEquals(prod.tags[0], "current")

        # test autonormalization of product install directories.
        # The install directory (PROD_DIR) for this python is given 
        # as a relative directory
        prod = self.db.findProduct("python", "2.5.2", "Linux")
        self.assert_(prod is not None)
        self.assertEquals(prod.name, "python")
        self.assertEquals(prod.version, "2.5.2")
        self.assertEquals(prod.flavor, "Linux")
        self.assertEquals(prod.db, os.path.join(testEupsStack, "ups_db"))
        expect_pdir = os.path.join(testEupsStack, "Linux/python/2.5.2")
        self.assertEquals(prod.dir, expect_pdir)
        expect_tfile = os.path.join(expect_pdir, "ups", "python.table")
        self.assertEquals(prod.tablefile, expect_tfile)

    def testFindProducts(self):
        prods = self.db.findProducts("doxygen")
        self.assertEquals(len(prods), 2)
        prod = filter(lambda d: d.version == "1.5.7.1", prods)[0]
        self.assertEquals(len(prod.tags), 1)
        self.assertEquals(prod.tags[0], "current")

        prods = self.db.findProducts("cfitsio")
        self.assertEquals(len(prods), 1)

        prods = self.db.findProducts("doxygen", flavors="Linux64")
        self.assertEquals(len(prods), 1)
        self.assertEquals(prods[0].version, "1.5.9")

        prods = self.db.findProducts("doxygen", "1.5.7.1")
        self.assertEquals(len(prods), 1)

    def testIsDeclared(self):
        self.assert_(self.db.isDeclared("doxygen"))
        self.assert_(self.db.isDeclared("doxygen", "1.5.9"))
        self.assert_(self.db.isDeclared("doxygen", "1.5.7.1"))
        self.assert_(self.db.isDeclared("doxygen", "1.5.9", "Linux64"))
        self.assert_(self.db.isDeclared("doxygen", flavor="Linux64"))
        self.assert_(self.db.isDeclared("doxygen", flavor="Linux"))
        self.assert_(not self.db.isDeclared("goober"))
        self.assert_(not self.db.isDeclared("goober", "1.0"))
        self.assert_(not self.db.isDeclared("doxygen", "1.5.10"))
        self.assert_(not self.db.isDeclared("doxygen", "1.5.9", "Linux"))

    def testAssignTag(self):
        if not os.path.exists(self.pycur+".bak"):
            shutil.copyfile(self.pycur, self.pycur+".bak")

        vers = self.db.getTaggedVersion("current", "python", "Linux")
        self.assertEquals(vers, "2.5.2")
        self.assertRaises(ProductNotFound, 
                          self.db.assignTag, "current", "python", "2.7")

        self.db.assignTag("current", "python", "2.6")
        self.assertEquals(self.db.getTaggedVersion("current","python","Linux"),
                          "2.6")
        self.db.assignTag("current", "python", "2.5.2")
        self.assertEquals(self.db.getTaggedVersion("current","python","Linux"),
                          "2.5.2")

        tfile = self.db._tagFile("python", "stable")
        if os.path.exists(tfile):  os.remove(tfile)
        try:
            self.db.assignTag("stable", "python", "2.6")
            self.assertEquals(self.db.getTaggedVersion("stable","python",
                                                       "Linux"),
                              "2.6")
            self.db.unassignTag("stable", "python", "Linux")
            self.assert_(not os.path.exists(tfile))
        except:
            if os.path.exists(tfile): os.remove(file)
            raise

        tfile = self.db._tagFile("doxygen", "beta")
        if os.path.exists(tfile):  os.remove(tfile)
        try: 
            self.db.assignTag("beta", "doxygen", "1.5.9")
            self.db.assignTag("beta", "doxygen", "1.5.7.1")
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64"),
                              "1.5.9")
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux"),
                              "1.5.7.1")        
            self.db.unassignTag("beta", "doxygen", "Linux64")
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux"),
                              "1.5.7.1")        
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64"),
                              None)        
            self.db.assignTag("beta", "doxygen", "1.5.9")
            self.db.unassignTag("beta", "doxygen", "Linux")
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64"),
                              "1.5.9")
            self.assertEquals(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux"),
                              None)        
            self.db.assignTag("beta", "doxygen", "1.5.7.1")
            self.db.unassignTag("beta", "doxygen")
            self.assert_(not os.path.exists(tfile))
        except:
            if os.path.exists(tfile):  os.remove(tfile)
            raise

        os.rename(self.pycur+".bak", self.pycur)

    def testDeclare(self):
        pdir = self.db._productDir("base")
        if os.path.isdir(pdir):  
            map(lambda r: os.remove(r),
                filter(lambda f: os.path.isfile(f), 
                       map(lambda p: os.path.join(pdir,p), os.listdir(pdir))))
            os.removedirs(pdir)
        try: 
            self.assert_(not os.path.exists(pdir))
            baseidir = os.path.join(testEupsStack,"Linux/base/1.0")
            base = Product("base", "1.0", "Linux", baseidir, 
                           os.path.join(baseidir, "ups/base.table"),
                           tags=["current"])
            self.db.declare(base)
            self.assert_(os.path.isdir(pdir))
            self.assert_(os.path.isfile(os.path.join(pdir,"1.0.version")))
            self.assert_(os.path.isfile(os.path.join(pdir,"current.chain")))
            prods = self.db.findProducts("base")
            self.assertEquals(len(prods), 1)
            self.assertEquals(prods[0].name, "base")
            self.assertEquals(prods[0].version, "1.0")
            self.assertEquals(prods[0].flavor, "Linux")
            self.assertEquals(prods[0].dir, baseidir)
            self.assertEquals(prods[0].tablefile, 
                              os.path.join(baseidir, "ups/base.table"))
            self.assertEquals(len(prods[0].tags), 1)
            self.assertEquals(prods[0].tags[0], "current")

            base2 = prods[0].clone()
            base2.version = "2.0"
            base2.tags = []
            self.db.declare(base2)
            self.assertEquals(self.db.getTaggedVersion("current", "base", 
                                                       "Linux"),
                              "1.0")
            base3 = prods[0].clone()
            base3.version = "3.0"
            self.db.declare(base3)
            self.assertEquals(self.db.getTaggedVersion("current", "base", 
                                                       "Linux"),
                              "3.0")

            self.assertEquals(len(self.db.findProducts("base")), 3)

            self.db.undeclare(base)
            self.assertEquals(self.db.findProduct("base","1.0","Linux"), None)
            self.assertEquals(len(self.db.findProducts("base")), 2)
            self.assert_(not os.path.exists(os.path.join(pdir,"1.0.version")))
            
            self.db.undeclare(base3)
            self.assertEquals(self.db.findProduct("base","3.0","Linux"), None)
            self.assertEquals(len(self.db.findProducts("base")), 1)
            self.assert_(not os.path.exists(os.path.join(pdir,"3.0.version")))
            self.assertEquals(self.db.getTaggedVersion("current", "base", 
                                                       "Linux"),
                              None)
            self.assert_(not os.path.exists(os.path.join(pdir,"current.chain")))
            self.db.undeclare(base2)
            self.assertEquals(len(self.db.findProducts("base")), 0)
            self.assert_(not os.path.exists(pdir))

        except:
            if False:
              if os.path.isdir(pdir): 
                map(lambda r: os.remove(r),
                    filter(lambda f: os.path.isfile(f), 
                           map(lambda p: os.path.join(pdir,p), 
                               os.listdir(pdir))))
                os.removedirs(pdir)
            raise
                           
__all__ = "VersionFileTestCase ChainFileTestCase DatabaseTestCase".split()

if __name__ == "__main__":
    unittest.main()
