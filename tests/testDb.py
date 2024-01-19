#!/usr/bin/env python
"""
Tests for eups.db
"""

import os
import shutil
import unittest
import testCommon
from testCommon import testEupsStack

from eups.Product import ProductNotFound, Product
from eups.db import VersionFile

class VersionFileTestCase(unittest.TestCase):

    def setUp(self):
        self.vf = VersionFile(os.path.join(testEupsStack, "fw.version"))

    def testParsing(self):
        self.assertEqual(self.vf.name, "fw")
        self.assertEqual(self.vf.version, "1.2")
        flavors = self.vf.getFlavors()
        self.assertEqual(len(flavors), 2)
        self.assertIn("DarwinX86", flavors)
        self.assertIn("Darwin", flavors)

        flavor = self.vf.info["DarwinX86"]
        self.assertEqual(flavor['declarer'], 'rhl')
        self.assertEqual(flavor['modifier'], 'rhl')
        self.assertEqual(flavor['productDir'], 'DarwinX86/fw/1.2')
        self.assertEqual(flavor['modified'], 'Tue Oct  9 22:05:03 2007')
        self.assertEqual(flavor['declared'], 'Tue Oct  9 22:05:03 2007')
        self.assertEqual(flavor['ups_dir'], '$PROD_DIR/ups')
        self.assertEqual(flavor['table_file'], 'fw.table')

        flavor = self.vf.info["Darwin"]
        self.assertEqual(flavor['declarer'], 'rhl')
        self.assertEqual(flavor['modifier'], 'rhl')
        self.assertEqual(flavor['productDir'], 'DarwinX86/fw/1.2')
        self.assertEqual(flavor['modified'], 'Tue Oct  9 22:05:03 2005')
        self.assertEqual(flavor['declared'], 'Tue Oct  9 22:05:03 2005')
        self.assertEqual(flavor['ups_dir'], '$PROD_DIR/ups')
        self.assertEqual(flavor['table_file'], 'fw.table')

        self.vf = VersionFile(os.path.join(testEupsStack, "fw.version"),
                              "afw", "3.2", verbosity=-1)
        self.assertEqual(self.vf.name, "afw")
        self.assertEqual(self.vf.version, "3.2")
        flavors = self.vf.getFlavors()
        self.assertEqual(len(flavors), 2)

    def testAddFlavor(self):
        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2",
                          "/opt/sw/Linux/fw/1.2/ups/fw.table")
        flavors = self.vf.getFlavors()
        self.assertEqual(len(flavors), 3)
        self.assertIn("Linux:rhel", flavors)
        info = self.vf.info["Linux:rhel"]
        self.assertEqual(info["table_file"], "fw.table")
        self.assertEqual(info["ups_dir"], "ups")
        self.assertEqual(info["productDir"], "/opt/sw/Linux/fw/1.2")
        self.assertIn("declarer", info)
        self.assertIn("declared", info)
        self.assertNotIn("modifier", info)
        declared = info["declared"]
        declarer = info["declarer"]

        self.vf.addFlavor("Linux:rhel", upsdir="ups")
        flavors = self.vf.getFlavors()
        self.assertEqual(len(flavors), 3)
        self.assertIn("Linux:rhel", flavors)
        info = self.vf.info["Linux:rhel"]
        self.assertEqual(info["table_file"], "fw.table")
        self.assertEqual(info["ups_dir"], "ups")
        self.assertEqual(info["productDir"], "/opt/sw/Linux/fw/1.2")
        self.assertEqual(info["declarer"], declarer)
        self.assertEqual(info["declared"], declared)
        self.assertEqual(info["modifier"], declarer)
        self.assertIn("modified", info)

        self.vf.removeFlavor("Linux:rhel")
        flavors = self.vf.getFlavors()
        self.assertEqual(len(flavors), 2)
        self.vf.removeFlavor(flavors)
        self.assertEqual(len(self.vf.getFlavors()), 0)
        self.assert_(self.vf.isEmpty())

    def testMakeProduct(self):
        prod = self.vf.makeProduct("Darwin")
        self.assertEqual(prod.name, "fw")
        self.assertEqual(prod.version, "1.2")
        self.assertEqual(prod.dir, "DarwinX86/fw/1.2")
        self.assertEqual(prod.flavor, "Darwin")
        self.assertEqual(prod.tablefile, "DarwinX86/fw/1.2/ups/fw.table")
        self.assertEqual(len(prod.tags), 0)
        self.assert_(prod.db is None)

        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2",
                          "/opt/sw/Linux/fw/1.2/ups/fw.table", "ups")
        prod = self.vf.makeProduct("Linux:rhel")
        self.assertEqual(prod.name, "fw")
        self.assertEqual(prod.version, "1.2")
        self.assertEqual(prod.dir, "/opt/sw/Linux/fw/1.2")
        self.assertEqual(prod.flavor, "Linux:rhel")
        self.assertEqual(prod.tablefile, "/opt/sw/Linux/fw/1.2/ups/fw.table")
        self.assertEqual(len(prod.tags), 0)
        self.assert_(prod.db is None)

        self.assertRaises(ProductNotFound, self.vf.makeProduct, "goober")

        prod = self.vf.makeProducts()
        self.assertEqual(len(prod), 3)
        for p in prod:
            self.assert_(isinstance(p, Product))

    def testWrite(self):
        self.vf.addFlavor("Linux:rhel", "/opt/sw/Linux/fw/1.2",
                          "/opt/sw/Linux/fw/1.2/ups/fw.table", "ups")

        self.assertEqual(len(self.vf.getFlavors()), 3)
        file=os.path.join(testEupsStack, "tst.version")
        self.vf.write(file=file)

        vf = VersionFile(file)
        self.assertEqual(vf.name, "fw")
        self.assertEqual(vf.version, "1.2")
        flavors = vf.getFlavors()
        self.assertEqual(len(flavors), 3)
        self.assertIn("DarwinX86", flavors)
        self.assertIn("Darwin", flavors)
        self.assertIn("Linux:rhel", flavors)

class MacroSubstitutionTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testPROD_ROOT(self):

        # test no substitution
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$PROD_ROOT/Linux/fw/1.0", "fw.table")
        prod = vf.makeProduct("Linux")
        self.assertEqual(prod.dir, "$PROD_ROOT/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "$PROD_ROOT/Linux/fw/1.0/fw.table")

        # test use in product dir
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/fw.table")

        # test integration of ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$PROD_ROOT/Linux/fw/1.0", "fw.table", "ups")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/ups/fw.table")

        # test use in table path
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$PROD_ROOT/Linux/fw/1.0",
                     "$PROD_ROOT/Linux/fw/1.0/fw.table", "ups")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/fw.table")

        # test use in ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$PROD_ROOT/Linux/fw/1.0",
                     "fw.table", "$PROD_ROOT/Linux/fw/1.0/UPS")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/UPS/fw.table")

        # test in combination with FLAVOR
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$PROD_ROOT/$FLAVOR/fw/1.0", "fw.table", "ups")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/LinuxARM/fw/1.0/ups/fw.table")

    def testFLAVOR(self):

        # test use in product dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "/opt/$FLAVOR/fw/1.0", "fw.table")
        prod = vf.makeProduct("LinuxARM")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/LinuxARM/fw/1.0/fw.table")

        # test use in product dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$FLAVOR/fw/1.0", "fw.table")
        prod = vf.makeProduct("LinuxARM")
        self.assertEqual(prod.dir, "LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "LinuxARM/fw/1.0/fw.table")

        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/LinuxARM/fw/1.0/fw.table")

        # test use in table path
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "Linux/fw/1.0", "$FLAVOR/fw.table",
                     "/opt/eups/tables")
        prod = vf.makeProduct("LinuxARM")
        self.assertEqual(prod.dir, "Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/eups/tables/LinuxARM/fw.table")

        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$FLAVOR/fw/1.0", "$FLAVOR/fw.table",
                     "/opt/eups/tables")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/eups/tables/LinuxARM/fw.table")

        # test use in ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$FLAVOR/fw/1.0", "fw.table")
        vf.info["LinuxARM"]["ups_dir"] = "$FLAVOR"
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/LinuxARM/fw/1.0/LinuxARM/fw.table")

        # test in combination with PROD_DIR
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$FLAVOR/fw/1.0", "fw.table", "$PROD_DIR/UPS")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/LinuxARM/fw/1.0/UPS/fw.table")

    def testPROD_DIR(self):
        # test in table
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "Linux/fw/1.0", "$PROD_DIR/fw.table")
        prod = vf.makeProduct("LinuxARM")
        self.assertEqual(prod.dir, "Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "Linux/fw/1.0/fw.table")

        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/fw.table")

        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "Linux/fw/1.0", "$PROD_DIR/fw.table", "ups")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/fw.table")

        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "Linux/fw/1.0", "$PROD_DIR/fw.table",
                     "$FLAVOR/ups")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/fw.table")

        # test in ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "Linux/fw/1.0", "fw.table", "$PROD_DIR/ups")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/ups/fw.table")

    def testUPS_DB(self):
        # test no substitution
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$UPS_DB/Linux/fw/1.0", "fw.table")
        prod = vf.makeProduct("Linux")
        self.assert_(prod.db is None)
        self.assertEqual(prod.dir, "$UPS_DB/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "$UPS_DB/Linux/fw/1.0/fw.table")

        # test use in product dir
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.db, "/opt/ups_db")
        self.assertEqual(prod.dir, "/opt/ups_db/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups_db/Linux/fw/1.0/fw.table")

        prod = vf.makeProduct("Linux", "/opt", "/opt/eups_db")
        self.assertEqual(prod.dir, "/opt/eups_db/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/eups_db/Linux/fw/1.0/fw.table")

        # test integration of ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$UPS_DB/Linux/fw/1.0", "fw.table", "ups")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.db, "/opt/ups_db")
        self.assertEqual(prod.dir, "/opt/ups_db/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups_db/Linux/fw/1.0/ups/fw.table")

        # test use in table path
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "/opt/Linux/fw/1.0",
                     "$UPS_DB/Linux/fw/1.0/fw.table", "ups")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.db, "/opt/ups_db")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups_db/Linux/fw/1.0/fw.table")

        # test use in ups_dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "Linux/fw/1.0",
                     "fw.table", "$UPS_DB/Linux/fw/1.0/UPS")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.db, "/opt/ups_db")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups_db/Linux/fw/1.0/UPS/fw.table")

        # test in combination with FLAVOR
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("LinuxARM", "$FLAVOR/fw/1.0", "fw.table",
                     "$UPS_DB/$FLAVOR/ups")
        prod = vf.makeProduct("LinuxARM", "/opt")
        self.assertEqual(prod.db, "/opt/ups_db")
        self.assertEqual(prod.dir, "/opt/LinuxARM/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups_db/LinuxARM/ups/fw.table")

    def testUPS_DIR(self):
        # test use in table path
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "/opt/Linux/fw/1.0",
                     "$UPS_DIR/fw.table", "UPS")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/Linux/fw/1.0/UPS/fw.table")

        # test no substitution
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$UPS_DIR/Linux/fw/1.0", "fw.table")
        prod = vf.makeProduct("Linux")
        self.assertEqual(prod.dir, "$UPS_DIR/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "$UPS_DIR/Linux/fw/1.0/fw.table")

        # test use in product dir
        vf = VersionFile(None, readFile=False)
        vf.addFlavor("Linux", "$UPS_DIR/Linux/fw/1.0", "fw.table",
                     "$PROD_ROOT/ups")
        prod = vf.makeProduct("Linux", "/opt")
        self.assertEqual(prod.dir, "/opt/ups/Linux/fw/1.0")
        self.assertEqual(prod.tablefile, "/opt/ups/fw.table")

    def testPROD_DIRfile(self):
        vf = VersionFile(os.path.join(testEupsStack, "fw.version"))
        prod = vf.makeProduct("Darwin")

        self.assertEqual(prod.dir, "DarwinX86/fw/1.2")
        self.assertEqual(prod.tablefile, "DarwinX86/fw/1.2/ups/fw.table")

    def testUPS_DBfile(self):
        vf = VersionFile(os.path.join(testEupsStack, "lapack-3.1.1.version"))
        prod = vf.makeProduct("Linux", "/opt")

        self.assertEqual(prod.dir, "/u/dss/products/Linux/lapack/3.1.1")
        self.assertEqual(prod.tablefile, "/opt/ups_db/lapack/Linux/3.1.1.table")

        prod = vf.makeProduct("Linux", dbpath="/opt/eups/UPS_DB")
        self.assertEqual(prod.tablefile, "/opt/eups/UPS_DB/lapack/Linux/3.1.1.table")

from eups.db import ChainFile

class ChainFileTestCase(unittest.TestCase):

    def setUp(self):
        self.cf = ChainFile(os.path.join(testEupsStack, "fw.current"))

    def testParsing(self):
        self.assertEqual(self.cf.name, "fw")
        self.assertEqual(self.cf.tag, "current")
        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 1)
        self.assertIn("DarwinX86", flavors)

        flavor = self.cf.info["DarwinX86"]
        self.assertEqual(flavor['declarer'], 'rhl')
        self.assertEqual(flavor['modifier'], 'rhl')
        self.assertEqual(flavor['version'], 'svn3941')
        self.assertEqual(flavor['modified'], 'Thu Jan 24 23:43:35 2008')
        self.assertEqual(flavor['declared'], 'Thu Jan 24 23:43:35 2008')

        self.assertEqual(self.cf.getVersion("DarwinX86"), "svn3941")

        self.cf = ChainFile(os.path.join(testEupsStack, "fw.current"),
                            "afw", "stable", verbosity=-1)
        self.assertEqual(self.cf.name, "afw")
        self.assertEqual(self.cf.tag, "stable")
        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 1)

    def testSetVersion(self):
        self.cf.setVersion("2.0", "Linux")

        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 2)
        self.assertIn("Linux", flavors)

        flavor = self.cf.info["Linux"]
        self.assertEqual(flavor['version'], '2.0')
        self.assert_(bool(flavor['declarer']))
        self.assert_(bool(flavor['declared']))
        self.assertNotIn('modifier', flavor)
        self.assertNotIn('modified', flavor)
        who = flavor['declarer']

        self.cf.setVersion("2.1", "Linux64")

        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 3)
        self.assertIn("Linux64", flavors)

        flavor = self.cf.info["Linux64"]
        self.assertEqual(flavor['version'], '2.1')
        self.assertEqual(flavor['declarer'], who)
        self.assert_(bool(flavor['declared']))
        self.assertNotIn('modifier', flavor)
        self.assertNotIn('modified', flavor)

        # an update to an existing flavor
        self.cf.setVersion("2.1", "DarwinX86")

        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 3)
        self.assertIn("DarwinX86", flavors)

        flavor = self.cf.info["DarwinX86"]
        self.assertEqual(flavor['version'], '2.1')
        self.assertEqual(flavor['declarer'], 'rhl')
        self.assertEqual(flavor['declared'], 'Thu Jan 24 23:43:35 2008')
        self.assertEqual(flavor['modifier'], who)
        self.assert_(bool(flavor['modified']))

        self.cf.removeVersion("Linux64")
        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 2)
        self.assertIn("DarwinX86", flavors)
        self.assertIn("Linux", flavors)

        self.cf.removeVersion()
        flavors = self.cf.getFlavors()
        self.assertEqual(len(flavors), 0)

        self.assert_(self.cf.hasNoAssignments())

    def testWrite(self):
        self.cf.setVersion("2.0", "Linux:rhel")
        self.assertEqual(len(self.cf.getFlavors()), 2)

        file=os.path.join(testEupsStack, "tst.current")
        self.cf.write(file)

        cf = ChainFile(file)
        self.assertEqual(cf.name, "fw")
        self.assertEqual(cf.tag, "current")
        flavors = cf.getFlavors()
        self.assertEqual(len(flavors), 2)
        self.assertIn("DarwinX86", flavors)

        flavor = cf.info["DarwinX86"]
        self.assertEqual(flavor['declarer'], 'rhl')
        self.assertEqual(flavor['modifier'], 'rhl')
        self.assertEqual(flavor['version'], 'svn3941')
        self.assertEqual(flavor['modified'], 'Thu Jan 24 23:43:35 2008')
        self.assertEqual(flavor['declared'], 'Thu Jan 24 23:43:35 2008')

        self.assertIn("Linux:rhel", flavors)


from eups.db import Database

class DatabaseTestCase(unittest.TestCase):

    def setUp(self):
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.userdb = os.path.join(testEupsStack, "user_ups_db")
        if not os.path.exists(self.userdb):
            os.makedirs(self.userdb)

        self.db = Database(self.dbpath, self.userdb)

        self.pycur = os.path.join(self.dbpath,"python","current.chain")
        if os.path.isfile(self.pycur+".bak"):
            os.rename(self.pycur+".bak", self.pycur)

    def tearDown(self):
        if os.path.isfile(self.pycur+".bak"):
            os.rename(self.pycur+".bak", self.pycur)

        if os.path.exists(self.userdb) and self.userdb.endswith("user_ups_db"):

            shutil.rmtree(self.userdb, ignore_errors=True)

    def testFindProductNames(self):
        prods = self.db.findProductNames()
        self.assertEqual(len(prods), 6)
        expected = "cfitsio tcltk eigen mpich2 python doxygen".split()
        for p in expected:
            self.assertIn(p, prods)

    def testFindVersions(self):
        vers = self.db.findVersions("goober")
        self.assertEqual(len(vers), 0)

        vers = self.db.findVersions("doxygen")
        self.assertEqual(len(vers), 2)
        expected = "1.5.7.1 1.5.9".split()
        for v in expected:
            self.assertIn(v, vers)

    def testFindFlavors(self):
        flavs = self.db.findFlavors("doxygen")
        self.assertEqual(len(flavs), 2)
        expected = "Linux Linux64".split()
        for f in expected:
            self.assertIn(f, flavs)

        flavs = self.db.findFlavors("doxygen", "1.5.9")
        self.assertEqual(len(flavs), 1)
        expected = "Linux64".split()
        for f in expected:
            self.assertIn(f, flavs)

        flavs = self.db.findFlavors("doxygen", "1.5.10")
        self.assertEqual(len(flavs), 0)

    def testFindTags(self):
        self.assertRaises(ProductNotFound, self.db.findTags,
                          "goober", "1.5.9", "Linux64")

        tags = self.db.findTags("doxygen", "1.5.10", "Linux64")
        self.assertEqual(len(tags), 0)

        tags = self.db.findTags("doxygen", "1.5.9", "Linux64")
        self.assertEqual(len(tags), 0)

        tags = self.db.findTags("doxygen", "1.5.7.1", "Linux")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "current")

    def testFindProduct(self):
        prod = self.db.findProduct("doxygen", "1.5.9", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("doxygen", "1.5.10", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("goober", "1.5.10", "Linux")
        self.assert_(prod is None)

        prod = self.db.findProduct("doxygen", "1.5.9", "Linux64")
        self.assert_(prod is not None)
        self.assertEqual(prod.name, "doxygen")
        self.assertEqual(prod.version, "1.5.9")
        self.assertEqual(prod.flavor, "Linux64")
        self.assertEqual(prod.db, os.path.join(testEupsStack, "ups_db"))
        self.assertEqual(prod.dir,
                "/lsst/DC3/stacks/gcc433/04jun/Linux64/external/doxygen/1.5.9")
        self.assertEqual(prod.tablefile, "/lsst/DC3/stacks/gcc433/04jun/Linux64/external/doxygen/1.5.9/ups/doxygen.table")
        self.assertEqual(len(prod.tags), 0)

        prod = self.db.findProduct("doxygen", "1.5.7.1", "Linux")
        self.assert_(prod is not None)
        self.assertEqual(prod.name, "doxygen")
        self.assertEqual(prod.version, "1.5.7.1")
        self.assertEqual(prod.flavor, "Linux")
        self.assertEqual(prod.db, os.path.join(testEupsStack, "ups_db"))
        self.assertEqual(prod.dir,
                "/home/rplante/wrk/NCSA/LSST/devlp/stacks/21mar/Linux/external/doxygen/1.5.7.1")
        self.assertEqual(prod.tablefile, "none")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "current")

        # test correct formation of table file path
        prod = self.db.findProduct("python", "2.5.2", "Linux")
        self.assertEqual(prod.name, "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor, "Linux")
        self.assertEqual(prod.db, os.path.join(testEupsStack, "ups_db"))
        self.assert_(prod.tablefile.endswith("Linux/python/2.5.2/ups/python.table"))
        self.assert_(os.path.exists(prod.tablefile))

        # test autonormalization of product install directories.
        # The install directory (PROD_DIR) for this python is given
        # as a relative directory
        prod = self.db.findProduct("python", "2.5.2", "Linux")
        self.assert_(prod is not None)
        self.assertEqual(prod.name, "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor, "Linux")
        self.assertEqual(prod.db, os.path.join(testEupsStack, "ups_db"))
        expect_pdir = os.path.join(testEupsStack, "Linux/python/2.5.2")
        self.assertEqual(prod.dir, expect_pdir)
        expect_tfile = os.path.join(expect_pdir, "ups", "python.table")
        self.assertEqual(prod.tablefile, expect_tfile)

    def testFindProducts(self):
        prods = self.db.findProducts("doxygen")
        self.assertEqual(len(prods), 2)
        prod = next(d for d in prods if d.version == "1.5.7.1") # this idiom efficiently returns the first element in a sequence
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "current")

        prods = self.db.findProducts("cfitsio")
        self.assertEqual(len(prods), 1)

        prods = self.db.findProducts("doxygen", flavors="Linux64")
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0].version, "1.5.9")

        prods = self.db.findProducts("doxygen", "1.5.7.1")
        self.assertEqual(len(prods), 1)

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

    def testUserTag(self):
        vers = self.db.getTaggedVersion("user:my", "python", "Linux")[1]
        self.assert_(vers is None)

        self.db.assignTag("user:my", "python", "2.5.2")
        vers = self.db.getTaggedVersion("user:my", "python", "Linux")[1]
        self.assertEqual(vers, "2.5.2")
        self.assert_(os.path.exists(os.path.join(self.userdb,
                                                 "python","my.chain")))

        tags = self.db.findTags("python", "2.5.2", "Linux")
        ntag = 2
        self.assertEqual(len(tags), ntag)
        self.assertEqual(tags.count("current"), 1)
        self.assertEqual(tags.count("user:my"), 1)

        prods = self.db.findProducts("python", "2.5.2")
        self.assertEqual(len(prods), 1)
        self.assertEqual(len(prods[0].tags), 2)
        self.assertEqual(tags[0], "current")
        self.assertEqual(tags[1], "user:my")

        self.db.unassignTag("user:my", "python")
        vers = self.db.getTaggedVersion("user:my", "python", "Linux")[1]
        self.assert_(vers is None)
        self.assert_(not os.path.exists(os.path.join(self.userdb,
                                                     "python","my.chain")))

    def testAssignTag(self):
        if not os.path.exists(self.pycur+".bak"):
            shutil.copyfile(self.pycur, self.pycur+".bak")

        vers = self.db.getTaggedVersion("current", "python", "Linux")[1]
        self.assertEqual(vers, "2.5.2")
        self.assertRaises(ProductNotFound,
                          self.db.assignTag, "current", "python", "2.7")

        self.db.assignTag("current", "python", "2.6")
        self.assertEqual(self.db.getTaggedVersion("current","python","Linux"),
                          ("python", "2.6"))
        self.db.assignTag("current", "python", "2.5.2")
        self.assertEqual(self.db.getTaggedVersion("current","python","Linux"),
                          ("python", "2.5.2"))

        tfile = self.db._tagFile("python", "stable")
        if os.path.exists(tfile):  os.remove(tfile)
        try:
            self.db.assignTag("stable", "python", "2.6")
            self.assertEqual(self.db.getTaggedVersion("stable","python",
                                                       "Linux"),
                              ("python", "2.6"))
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
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64")[1],
                              "1.5.9")
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux")[1],
                              "1.5.7.1")
            self.db.unassignTag("beta", "doxygen", "Linux64")
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux")[1],
                              "1.5.7.1")
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64")[1],
                              None)
            self.db.assignTag("beta", "doxygen", "1.5.9")
            self.db.unassignTag("beta", "doxygen", "Linux")
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux64")[1],
                              "1.5.9")
            self.assertEqual(self.db.getTaggedVersion("beta","doxygen",
                                                       "Linux")[1],
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
            for p in os.listdir(pdir):
                f = os.path.join(pdir, p)
                if os.path.isfile(f):
                    os.remove(f)
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
            self.assertEqual(len(prods), 1)
            self.assertEqual(prods[0].name, "base")
            self.assertEqual(prods[0].version, "1.0")
            self.assertEqual(prods[0].flavor, "Linux")
            self.assertEqual(prods[0].dir, baseidir)
            self.assertEqual(prods[0].tablefile,
                              os.path.join(baseidir, "ups/base.table"))
            self.assertEqual(len(prods[0].tags), 1)
            self.assertEqual(prods[0].tags[0], "current")

            base2 = prods[0].clone()
            base2.version = "2.0"
            base2.tags = []
            self.db.declare(base2)
            self.assertEqual(self.db.getTaggedVersion("current", "base",
                                                       "Linux"),
                              ("base", "1.0"))
            base3 = prods[0].clone()
            base3.version = "3.0"
            self.db.declare(base3)
            self.assertEqual(self.db.getTaggedVersion("current", "base",
                                                       "Linux"),
                              ("base", "3.0"))

            self.assertEqual(len(self.db.findProducts("base")), 3)

            self.db.undeclare(base)
            self.assertEqual(self.db.findProduct("base","1.0","Linux"), None)
            self.assertEqual(len(self.db.findProducts("base")), 2)
            self.assert_(not os.path.exists(os.path.join(pdir,"1.0.version")))

            self.db.undeclare(base3)
            self.assertEqual(self.db.findProduct("base","3.0","Linux"), None)
            self.assertEqual(len(self.db.findProducts("base")), 1)
            self.assert_(not os.path.exists(os.path.join(pdir,"3.0.version")))
            self.assertEqual(self.db.getTaggedVersion("current", "base",
                                                       "Linux")[1],
                              None)
            self.assert_(not os.path.exists(os.path.join(pdir,"current.chain")))
            self.db.undeclare(base2)
            self.assertEqual(len(self.db.findProducts("base")), 0)
            self.assert_(not os.path.exists(pdir))

        except:
            if False:
              if os.path.isdir(pdir):
                  for p in os.listdir(pdir):
                      f = os.path.join(pdir, p)
                      if os.path.isfile(f):
                          os.remove(f)
                  os.removedirs(pdir)
            raise

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        ChainFileTestCase,
        DatabaseTestCase,
        MacroSubstitutionTestCase,
        VersionFileTestCase,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
