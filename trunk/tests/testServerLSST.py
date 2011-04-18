#!/usr/bin/env python
"""
Tests for eups.server, focussing on local (cp) tranport mechanisms
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import shutil
import unittest
import time
from testCommon import testEupsStack

from eups.distrib.server import Transporter, LocalTransporter
from eups.distrib.server import RemoteFileNotFound
from eups.distrib.server import ConfigurableDistribServer
import eups, eups.cmd

# the package server root:
pkgroot = "http://dev.lsstcorp.org/dmspkgs"
bootroot = "http://dev.lsstcorp.org/dmspkgs/bootstrap"
prog = "eups"

from eups.distrib.server import DistribServer 

class LsstConfigFileTestCase(unittest.TestCase):

    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.base = os.path.join(testEupsStack, "testserver", "s2")
        self.configFile = os.path.join(testEupsStack, "eups-config.txt")

    def tearDown(self):
        if os.path.exists(self.configFile):
            os.remove(self.configFile)

    def testGetConfigFile(self):
        ds = DistribServer(self.base)
        configFile = ds.getConfigFile(self.configFile)
        self.assert_(os.path.exists(configFile))

        

from eups.distrib.server import ServerConf

class LsstServerConfTestCase(unittest.TestCase):

    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.pkgroot = pkgroot
        self.servconf = ServerConf(self.pkgroot)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class LsstDistribServerTestCase(unittest.TestCase):

    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.pkgroot = pkgroot

        # an empty config file
        self.configFile = os.path.join(testEupsStack,"testserver","s2",
                                       "config.txt")
        self.assert_(os.path.isfile(self.configFile))

        conf = ServerConf(self.pkgroot, configFile=self.configFile)
        self.ds = conf.createDistribServer()

    def tearDown(self):
        pass

    def testInit(self):
        self.assert_(isinstance(self.ds, ConfigurableDistribServer), 
                     "factory did not return ConfigurableDistribServer")
        self.assertEquals(self.ds.getConfigProperty("PREFER_GENERIC",""), '')

    def testListAvailProds(self):
        prods = self.ds.listAvailableProducts()
        self.assert_(len(prods) > 300)

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
#        print "tags:", tags
        self.assertEquals(len(tags), 3)
        self.assert_("current" in tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 3)
        self.assert_("current" in tags)
        self.assert_("active" in tags)
        self.assert_("alpha" in tags)

    def testGetManifest(self):
        man = self.ds.getManifest("doxygen", "1.5.9", "generic")
        self.assert_(man is not None)
        self.assertEquals(man.product, "doxygen")
        self.assertEquals(man.version, "1.5.9")
        self.assertEquals(len(man.getProducts()), 1)
        prod = man.getDependency("doxygen", "1.5.9")
        self.assertEquals(man.product, "doxygen")
        self.assertEquals(man.version, "1.5.9")

    def testGetTaggedProductInfo(self):
        info = self.ds.getTaggedProductInfo("cfitsio", "generic",tag="current")
        self.assertEquals(info[0], "cfitsio")
        self.assertEquals(info[2], "3006.2")
        info = self.ds.getTaggedProductInfo("cfitsio", "generic",tag="current")
        self.assertEquals(info[0], "cfitsio")
        self.assertEquals(info[2], "3006.2")

    def testGetTagNamesFor(self):
        tags = self.ds.getTagNamesFor("cfitsio", "3006.2")
        self.assertEquals(len(tags), 1)
        self.assertEquals(tags[0], "current")

from eups.distrib.Repository import Repository
from eups.Eups import Eups
from eups.tags import Tag

class LsstRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
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
        self.assert_(self.repos.distServer, DistribServer)

    def testIsWritable(self):
        self.assert_(not self.repos.isWritable())

    def testGetManifest(self):
        man = self.repos.getManifest("doxygen", "1.5.9", "generic")
        self.assert_(man is not None)

    def testListPackages(self):
        pkgs = self.repos.listPackages()
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assert_(len(pkgs) > 300)

    def testGetSupportedTags(self):
        tags = self.repos.getSupportedTags()
        self.assertEquals(len(tags), 3)
        self.assert_("current" in tags)
        self.assert_("active" in tags)
        self.assert_("alpha" in tags)

    def testFindPackage(self):
        pkg = self.repos.findPackage("doxygen")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.4")
        self.assertEquals(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.9")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "Linux")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "generic")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")

        tag = Tag("newest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")

from eups.distrib.Repositories import Repositories

class LsstRepositoriesTestCase(unittest.TestCase):
    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
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
        self.assertEquals(len(self.repos.pkgroots), 2)

        pkg = self.repos.findPackage("doxygen")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.lsstroot)

        pkg = self.repos.findPackage("doxygen", "1.5.9")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.lsstroot)

        pkg = self.repos.findPackage("doxygen", "1.5.8")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.localroot)

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "Linux")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.9", "generic")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.lsstroot)

        tag = Tag("newest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.9")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.lsstroot)

    def testListPackages(self):
        self.repos = Repositories([self.localroot, self.lsstroot],
                                  eupsenv=self.eups, options=self.opts)
        self.assertEquals(len(self.repos.pkgroots), 2)

        pkgs = self.repos.listPackages()
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 2)           # the # of repositories
        self.assertEquals(len(pkgs[0]), 2)        # (pkgroot, pkg-list)
        self.assertEquals(len(pkgs[1]), 2)        # (pkgroot, pkg-list)
        self.assertEquals(len(pkgs[0][1]), 1)     # # of products per repos.
        self.assertEquals(len(pkgs[0][1][0]), 3)  # # of attrs per product
        self.assertEquals(pkgs[0][1][0][0], "doxygen")
        self.assertEquals(pkgs[0][1][0][1], "1.5.8")
        self.assertEquals(pkgs[0][1][0][2], "generic")
        self.assert_(len(pkgs[1][1]) > 300)       # # of products per repos.

        pkgs = self.repos.listPackages("doxygen")
        pkgs = self.repos.listPackages("doxygen")
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(len(pkgs[0][1]), 1)     # # of products per repos.
        self.assertEquals(pkgs[0][1][0][0], "doxygen")
        self.assertEquals(pkgs[0][1][0][1], "1.5.8")
        self.assertEquals(pkgs[0][1][0][2], "generic")
        self.assertEquals(len(pkgs[1][1]), 5)     # # of products per repos.
        self.assertEquals(pkgs[1][1][0][0], "doxygen")
        self.assertEquals(pkgs[1][1][0][1], "1.5.4")
        self.assertEquals(pkgs[1][1][1][1], "1.5.7.1")
        self.assertEquals(pkgs[1][1][4][1], "1.5.9")
        self.assertEquals(pkgs[1][1][2][1], "1.5.8")
        self.assertEquals(pkgs[1][1][3][1], "1.5.8+1")

class LsstCmdTestCase(unittest.TestCase):

    def setUp(self):
        if not os.environ.has_key("EUPS_DIR"):
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
        self.assert_(prod is None)

        cmd = "distrib install lssteups 1.1 -q -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assert_(prod is not None)
        self.assertEquals(prod.version, "1.1")
        self.assert_(prod.dir.endswith("lssteups/1.1"))
        self.assert_(os.path.exists(prod.dir))
        pdir = prod.dir

        cmd = "remove lssteups 1.1"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assert_(prod is None)
        
        cmd = "distrib install lssteups 1.1 --noclean -q -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)

        prod = Eups().findProduct("lssteups")
        self.assert_(prod is not None)
        bdir = os.path.join(testEupsStack,"EupsBuildDir",self.flavor,"lssteups-1.1")
        self.assert_(os.path.exists(bdir), "%s does not exist" % bdir)

        cmd = "distrib clean lssteups 1.1 -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assert_(not os.path.exists(bdir), "%s still exists" % bdir)

        cmd = "distrib clean lssteups 1.1 -q -R -r " + self.lsstroot
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assert_(not os.path.exists(bdir), "%s still exists" % bdir)

        prod = Eups().findProduct("lssteups")
        self.assert_(prod is None)
        self.assert_(not os.path.exists(pdir))
        

__all__ = "LsstConfigFileTestCase LsstServerConfTestCase LsstDistribServerTestCase LsstRepositoryTestCase LsstRepositoriesTestCase".split()        

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkgroot = bootroot = sys.argv[1]
    unittest.main()
