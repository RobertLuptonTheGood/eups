#!/usr/bin/env python
"""
Tests for eups.server, focussing on local (cp) tranport mechanisms
"""

import os
import unittest
from testCommon import testEupsStack

from eups.distrib.server import Transporter, LocalTransporter
from eups.distrib.server import ConfigurableDistribServer

class LocalTransporterTestCase(unittest.TestCase):

    def setUp(self):
        self.base = "http://dev.lsstcorp.org/eupstest/"
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)

    def testGenericTransporter(self):
        loc = self.base+"s1/config.txt"
        localfile = "/tmp/eupstest-config.txt"
        self.assert_(not Transporter.canHandle(loc))
        if os.path.exists(localfile):
            os.remove(localfile)
        trx = Transporter(loc)
        self.assertRaises(Exception, trx.listDir)
        self.assertRaises(Exception, trx.cacheToFile, localfile)
        self.assert_(not os.path.exists(localfile))
        self.assertRaises(Exception, trx.listDir)

    def testLocalTransporter(self):
        base = os.path.join(testEupsStack,"testserver")
        loc = os.path.join(base,"s1","config.txt")
        localfile = "/tmp/eupstest-config.txt"
        if os.path.exists(localfile):
            os.remove(localfile)
        self.assert_(LocalTransporter.canHandle(loc))

        trx = LocalTransporter(loc)
#        self.assertRaises(RemoteFileNotFound, trx.cacheToFile, localfile)
        self.assert_(not os.path.exists(localfile))

        loc = os.path.join(base,"s2","config.txt")
        trx = LocalTransporter(loc)
        trx.cacheToFile(localfile)
        self.assert_(os.path.exists(localfile))
        
        loc = os.path.join(base,"s2")
        trx = LocalTransporter(loc)
        files = trx.listDir()
        self.assertEquals(len(files), 2)
        self.assertIn("config.txt", files)
        self.assertIn("current.list", files)

from eups.distrib.server import DistribServer 

class LocalConfigFileTestCase(unittest.TestCase):

    def setUp(self):
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

class LocalServerConfTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgbase = os.path.join(testEupsStack, "testserver", "s2")
        self.servconf = ServerConf(self.pkgbase)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class LocalDistribServerTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgbase = os.path.join(testEupsStack, "testserver", "s2")
        self.ds = ServerConf.makeServer(self.pkgbase, False)

    def tearDown(self):
        pass

    def testInit(self):
        self.assert_(isinstance(self.ds, ConfigurableDistribServer), 
                     "factory did not return ConfigurableDistribServer")
        self.assertEquals(self.ds.getConfigProperty("PREFER_GENERIC",""), '')

    def testListAvailProds(self):
        prods = self.ds.listAvailableProducts()
        self.assertEquals(len(prods), 1)
        self.assertEquals(prods[0][0], "doxygen")
        self.assertEquals(prods[0][1], "1.5.8")
        self.assertEquals(prods[0][2], "generic")

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
        self.assertEquals(len(tags), 1)
        self.assertIn("current", tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 1)
        self.assertIn("current", tags)

        # test configurable impl. (method 2)
        self.ds.setConfigProperty("AVAILABLE_TAGS_URL", 
                                  "%(base)s/info/tagnames.txt")
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 3)
        self.assertIn("current", tags)
        self.assertIn("beta", tags)
        self.assertIn("stable", tags)

        # test configurable impl. (method 1)
        self.ds.setConfigProperty("AVAILABLE_TAGS", "current beta")
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 2)
        self.assertIn("current", tags)
        self.assertIn("beta", tags)

from eups.distrib.Repository import Repository
from eups.Eups import Eups
from eups.tags import Tag

class LocalRepositoryTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgroot = os.path.join(testEupsStack, "testserver", "s2")
        self.eups = Eups()
        self.repos = Repository(self.eups, self.pkgroot)

    def tearDown(self):
        pass

    def testInit(self):
        self.assert_(self.repos.distServer, DistribServer)

    def testIsWritable(self):
        self.assert_(self.repos.isWritable())

    def testGetManifest(self):
        man = self.repos.getManifest("doxygen", "1.5.8", "generic")
        self.assert_(man is not None)

    def testListPackages(self):
        pkgs = self.repos.listPackages()
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0][0], "doxygen")
        self.assertEquals(pkgs[0][1], "1.5.8")
        self.assertEquals(pkgs[0][2], "generic")

        pkgs = self.repos.listPackages("doxygen")
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 1)
        self.assertEquals(pkgs[0][0], "doxygen")
        self.assertEquals(pkgs[0][1], "1.5.8")
        self.assertEquals(pkgs[0][2], "generic")

        pkgs = self.repos.listPackages("doxygen", "1.5.10")
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 0)

    def testGetSupportedTags(self):
        tags = self.repos.getSupportedTags()
        self.assertEquals(len(tags), 1)
        self.assertIn("current", tags)

    def testFindPackage(self):
        pkg = self.repos.findPackage("doxygen")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.8")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.8", "Linux")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.8", "generic")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")

        tag = Tag("newest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")

from eups.distrib.Repositories import Repositories

class LocalRepositoriesTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgroot = os.path.join(testEupsStack, "testserver", "s2")
        self.eups = Eups()
        self.repos = Repositories("|".join([self.pkgroot, self.pkgroot]),
                                  eupsenv=self.eups)

    def tearDown(self):
        pass

    def testInit(self):
        self.assertEquals(len(self.repos.pkgroots), 2)

    def testListPackages(self):
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
        self.assertEquals(pkgs[1][1][0][0], "doxygen")
        self.assertEquals(pkgs[1][1][0][1], "1.5.8")
        self.assertEquals(pkgs[1][1][0][2], "generic")

        pkgs = self.repos.listPackages("doxygen")
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(pkgs[0][1][0][0], "doxygen")
        self.assertEquals(pkgs[0][1][0][1], "1.5.8")
        self.assertEquals(pkgs[0][1][0][2], "generic")

        pkgs = self.repos.listPackages("doxygen", "1.5.10")
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 2)           # the # of repositories
        self.assertEquals(len(pkgs[0][1]), 0)     # # of products per repos.
        self.assertEquals(len(pkgs[1][1]), 0)     # # of products per repos.

        tag = Tag("newest")
        pkgs = self.repos.listPackages("doxygen", tag)
        self.assert_(pkgs is not None)
        self.assert_(isinstance(pkgs, list))
        self.assertEquals(len(pkgs), 2)
        self.assertEquals(pkgs[0][1][0][0], "doxygen")
        self.assertEquals(pkgs[0][1][0][1], "1.5.8")
        self.assertEquals(pkgs[0][1][0][2], "generic")
        self.assertEquals(pkgs[1][1][0][0], "doxygen")
        self.assertEquals(pkgs[1][1][0][1], "1.5.8")
        self.assertEquals(pkgs[1][1][0][2], "generic")

    def testFindPackage(self):
        pkg = self.repos.findPackage("doxygen")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")

        pkg = self.repos.findPackage("doxygen", "1.5.8")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.pkgroot)

        pkg = self.repos.findPackage("doxygen", "1.5.0")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.8", "Linux")
        self.assert_(pkg is None)

        pkg = self.repos.findPackage("doxygen", "1.5.8", "generic")
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.pkgroot)

        tag = Tag("newest")
        pkg = self.repos.findPackage("doxygen", tag)
        self.assert_(pkg is not None)
        self.assertEquals(pkg[0], "doxygen")
        self.assertEquals(pkg[1], "1.5.8")
        self.assertEquals(pkg[2], "generic")
        self.assertEquals(pkg[3], self.pkgroot)



__all__ = "LocalTransporterTestCase LocalConfigFileTestCase LocalServerConfTestCase LocalDistribServerTestCase LocalRepositoryTestCase LocalRepositoriesTestCase".split()        

if __name__ == "__main__":
    unittest.main()
