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

# the package server root:
pkgroot = "http://dev.lsstcorp.org/dmspkgs"

from eups.distrib.server import DistribServer 

class LsstConfigFileTestCase(unittest.TestCase):

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

class LsstServerConfTestCase(unittest.TestCase):

    def setUp(self):
        self.pkgroot = pkgroot
        self.servconf = ServerConf(self.pkgroot)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class LsstDistribServerTestCase(unittest.TestCase):

    def setUp(self):
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
        self.assertEquals(len(tags), 2)
        self.assert_("current" in tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 2)
        self.assert_("current" in tags)
        self.assert_("active" in tags)

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


__all__ = "LsstConfigFileTestCase LsstServerConfTestCase LsstDistribServerTestCase".split()        

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkgroot = sys.argv[1]
    unittest.main()
