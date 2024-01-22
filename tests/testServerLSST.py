#!/usr/bin/env python
"""
Tests for eups.server, focussing on local (cp) tranport mechanisms
"""

import os
import sys
import unittest
from testCommon import testEupsStack

from eups.distrib.server import ConfigurableDistribServer
import eups, eups.cmd

# the package server root:
pkgroot = "http://dev.lsstcorp.org/dmspkgs"
bootroot = "http://dev.lsstcorp.org/dmspkgs/bootstrap"
prog = "eups"

from eups.distrib.server import DistribServer

class LsstConfigFileTestCase(unittest.TestCase):

    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.base = os.path.join(testEupsStack, "testserver", "s2")
        self.configFile = os.path.join(testEupsStack, "eups-config.txt")

    def tearDown(self):
        if os.path.exists(self.configFile):
            os.remove(self.configFile)

    def testGetConfigFile(self):
        ds = DistribServer(self.base)
        configFile = ds.getConfigFile(self.configFile)
        self.assertTrue(os.path.exists(configFile))



from eups.distrib.server import ServerConf

class LsstServerConfTestCase(unittest.TestCase):

    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.pkgroot = pkgroot
        self.servconf = ServerConf(self.pkgroot)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class LsstDistribServerTestCase(unittest.TestCase):

    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.pkgroot = pkgroot

        # an empty config file
        self.configFile = os.path.join(testEupsStack,"testserver","s2",
                                       "config.txt")
        self.assertTrue(os.path.isfile(self.configFile))

        conf = ServerConf(self.pkgroot, configFile=self.configFile)
        self.ds = conf.createDistribServer()

    def tearDown(self):
        pass

    def testInit(self):
        self.assertTrue(isinstance(self.ds, ConfigurableDistribServer),
                     "factory did not return ConfigurableDistribServer")
        self.assertEqual(self.ds.getConfigProperty("PREFER_GENERIC",""), '')

    def testListAvailProds(self):
        prods = self.ds.listAvailableProducts()
        self.assertTrue(len(prods) > 300)

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
#        print "tags:", tags
        self.assertEqual(len(tags), 3)
        self.assertIn("current", tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEqual(len(tags), 3)
        self.assertIn("current", tags)
        self.assertIn("active", tags)
        self.assertIn("alpha", tags)

    def testGetManifest(self):
        man = self.ds.getManifest("doxygen", "1.5.9", "generic")
        self.assertIsNotNone(man)
        self.assertEqual(man.product, "doxygen")
        self.assertEqual(man.version, "1.5.9")
        self.assertEqual(len(man.getProducts()), 1)
        man.getDependency("doxygen", "1.5.9")
        self.assertEqual(man.product, "doxygen")
        self.assertEqual(man.version, "1.5.9")

    def testGetTaggedProductInfo(self):
        info = self.ds.getTaggedProductInfo("cfitsio", "generic",tag="current")
        self.assertEqual(info[0], "cfitsio")
        self.assertEqual(info[2], "3006.2")
        info = self.ds.getTaggedProductInfo("cfitsio", "generic",tag="current")
        self.assertEqual(info[0], "cfitsio")
        self.assertEqual(info[2], "3006.2")

    def testGetTagNamesFor(self):
        tags = self.ds.getTagNamesFor("cfitsio", "3006.2")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "current")

from eups.distrib.Repository import Repository
from eups.Eups import Eups
from eups.tags import Tag

class LsstRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.pkgroot = pkgroot
        self.eups = Eups()
        self.opts = { "serverconf":
                      { "DISTRIB_SERVER_CLASS": "eups.distrib.server.ConfigurableDistribServer",
                        "DISTRIB_CLASS": "eups.distrib.Distrib.DefaultDistrib" }
                      }
        self.repos = Repository(self.eups, self.pkgroot, options=self.opts)

    def tearDown(self):
        pass

    def testInit(self):
        self.assertTrue(self.repos.distServer, DistribServer)

    def testIsWritable(self):
        self.assertTrue(not self.repos.isWritable())

    def testGetManifest(self):
        man = self.repos.getManifest("doxygen", "1.5.9", "generic")
        self.assertIsNotNone(man)

    def testListPackages(self):
        pkgs = self.repos.listPackages()
        self.assertIsNotNone(pkgs)
        self.assertTrue(isinstance(pkgs, list))
        self.assertTrue(len(pkgs) > 300)

    def testGetSupportedTags(self):
        tags = self.repos.getSupportedTags()
        self.assertEqual(len(tags), 3)
        self.assertIn("current", tags)
        self.assertIn("active", tags)
        self.assertIn("alpha", tags)

    def testFindPackage(self):
        pkg = self.repos.findPackage("doxygen")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.4")
        self.assertEqual(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.9")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assertIsNone(pkg)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "Linux")
        self.assertIsNone(pkg)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "generic")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")

        tag = Tag("latest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")

from eups.distrib.Repositories import Repositories

class LsstRepositoriesTestCase(unittest.TestCase):
    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.localroot = os.path.join(testEupsStack, "testserver", "s2")
        self.lsstroot = pkgroot
        self.eups = Eups()
        self.opts = { "serverconf":
                      { "DISTRIB_SERVER_CLASS": "eups.distrib.server.ConfigurableDistribServer",
                        "DISTRIB_CLASS": "eups.distrib.Distrib.DefaultDistrib" }
                      }

    def tearDown(self):
        pass

    def testFindPackage1(self):
        self.repos = Repositories([self.localroot, self.lsstroot],
                                  eupsenv=self.eups, options=self.opts)
        self.assertEqual(len(self.repos.pkgroots), 2)

        pkg = self.repos.findPackage("doxygen")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")
        self.assertEqual(pkg[3], self.lsstroot)

        pkg = self.repos.findPackage("doxygen", "1.5.9")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")
        self.assertEqual(pkg[3], self.lsstroot)

        pkg = self.repos.findPackage("doxygen", "1.5.8")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.8")
        self.assertEqual(pkg[2], "generic")
        self.assertEqual(pkg[3], self.localroot)

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assertIsNone(pkg)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "Linux")
        self.assertIsNone(pkg)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "generic")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")
        self.assertEqual(pkg[3], self.lsstroot)

        tag = Tag("latest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg[0], "doxygen")
        self.assertEqual(pkg[1], "1.5.9")
        self.assertEqual(pkg[2], "generic")
        self.assertEqual(pkg[3], self.lsstroot)

    def testListPackages(self):
        self.repos = Repositories([self.localroot, self.lsstroot],
                                  eupsenv=self.eups, options=self.opts)
        self.assertEqual(len(self.repos.pkgroots), 2)

        pkgs = self.repos.listPackages()
        self.assertIsNotNone(pkgs)
        self.assertTrue(isinstance(pkgs, list))
        self.assertEqual(len(pkgs), 2)           # the # of repositories
        self.assertEqual(len(pkgs[0]), 2)        # (pkgroot, pkg-list)
        self.assertEqual(len(pkgs[1]), 2)        # (pkgroot, pkg-list)
        self.assertEqual(len(pkgs[0][1]), 1)     # # of products per repos.
        self.assertEqual(len(pkgs[0][1][0]), 3)  # # of attrs per product
        self.assertEqual(pkgs[0][1][0][0], "doxygen")
        self.assertEqual(pkgs[0][1][0][1], "1.5.8")
        self.assertEqual(pkgs[0][1][0][2], "generic")
        self.assertTrue(len(pkgs[1][1]) > 300)       # # of products per repos.

        pkgs = self.repos.listPackages("doxygen")
        pkgs = self.repos.listPackages("doxygen")
        self.assertIsNotNone(pkgs)
        self.assertTrue(isinstance(pkgs, list))
        self.assertEqual(len(pkgs), 2)
        self.assertEqual(len(pkgs[0][1]), 1)     # # of products per repos.
        self.assertEqual(pkgs[0][1][0][0], "doxygen")
        self.assertEqual(pkgs[0][1][0][1], "1.5.8")
        self.assertEqual(pkgs[0][1][0][2], "generic")
        self.assertEqual(len(pkgs[1][1]), 5)     # # of products per repos.
        self.assertEqual(pkgs[1][1][0][0], "doxygen")
        self.assertEqual(pkgs[1][1][0][1], "1.5.4")
        self.assertEqual(pkgs[1][1][1][1], "1.5.7.1")
        self.assertEqual(pkgs[1][1][4][1], "1.5.9")
        self.assertEqual(pkgs[1][1][2][1], "1.5.8")
        self.assertEqual(pkgs[1][1][3][1], "1.5.8+1")

class LsstCmdTestCase(unittest.TestCase):

    def setUp(self):
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.localroot = os.path.join(testEupsStack, "testserver", "s2")
        self.lsstroot = bootroot
        os.environ["EUPS_PATH"] = testEupsStack
        self.flavor = eups.flavor()

    def tearDown(self):
        lssteups = [ os.path.join(testEupsStack,"ups_db","lssteups"),
                     os.path.join(testEupsStack,"EupsBuildDir",
                                  self.flavor,"lssteups-1.1"),
                     os.path.join(testEupsStack,self.flavor,"lssteups") ]
        for pdir in lssteups:
            if os.path.exists(pdir):
                for dir,subdirs,files in os.walk(pdir, False):
                    for file in files:
                        os.remove(os.path.join(dir,file))
                    for file in subdirs:
                        os.rmdir(os.path.join(dir,file))
                os.rmdir(pdir)


    def testInstall(self):
        prod = Eups().findProduct("lssteups")
        self.assertIsNone(prod)

        cmd = "distrib install lssteups 1.1 -q -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assertIsNotNone(prod)
        self.assertEqual(prod.version, "1.1")
        self.assertTrue(prod.dir.endswith("lssteups/1.1"))
        self.assertTrue(os.path.exists(prod.dir))
        pdir = prod.dir

        cmd = "remove lssteups 1.1"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assertIsNone(prod)

        cmd = "distrib install lssteups 1.1 --noclean -q -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assertIsNotNone(prod)
        bdir = os.path.join(testEupsStack,"EupsBuildDir",self.flavor,"lssteups-1.1")
        self.assertTrue(os.path.exists(bdir), "%s does not exist" % bdir)

        cmd = "distrib clean lssteups 1.1 -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertTrue(not os.path.exists(bdir), "%s still exists" % bdir)

        cmd = "distrib clean lssteups 1.1 -q -R -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertTrue(not os.path.exists(bdir), "%s still exists" % bdir)

        prod = Eups().findProduct("lssteups")
        self.assertIsNone(prod)
        self.assertTrue(not os.path.exists(pdir))


__all__ = "LsstConfigFileTestCase LsstServerConfTestCase LsstDistribServerTestCase LsstRepositoryTestCase LsstRepositoriesTestCase".split()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkgroot = bootroot = sys.argv[1]
    unittest.main()
