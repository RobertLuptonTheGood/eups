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

class LocalTransporterTestCase(unittest.TestCase):

    def setUp(self):
        self.base = "http://dev.lsstcorp.org/eupstest/"
        if not os.environ.has_key("EUPS_DIR"):
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
        self.assert_("config.txt" in files)
        self.assert_("current.list" in files)

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
        self.pkgbase = os.path.join(testEupsStack, "testserver", "s2")
        self.servconf = ServerConf(self.pkgbase)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class LocalDistribServerTestCase(unittest.TestCase):

    def setUp(self):
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
        self.assertEquals(len(prods), 0)

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
        self.assertEquals(len(tags), 1)
        self.assert_("current" in tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 1)
        self.assert_("current" in tags)

        # test configurable impl. (method 2)
        self.ds.setConfigProperty("AVAILABLE_TAGS_URL", 
                                  "%(base)s/info/tagnames.txt")
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 3)
        self.assert_("current" in tags)
        self.assert_("beta" in tags)
        self.assert_("stable" in tags)

        # test configurable impl. (method 1)
        self.ds.setConfigProperty("AVAILABLE_TAGS", "current beta")
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 2)
        self.assert_("current" in tags)
        self.assert_("beta" in tags)




__all__ = "LocalTransporterTestCase LocalConfigFileTestCase LocalServerConfTestCase LocalDistribServerTestCase".split()        

if __name__ == "__main__":
    unittest.main()
