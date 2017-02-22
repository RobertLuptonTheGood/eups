#!/usr/bin/env python
"""
Tests for eups.server, focussing on web tranport mechanisms
"""

import os
import sys
import unittest
from testCommon import testEupsStack

from eups.distrib.server import WebTransporter
from eups.distrib.server import RemoteFileNotFound

# the package server root:
pkgroot = "http://dev.lsstcorp.org/eupstest"

class WebTransporterTestCase(unittest.TestCase):

    def setUp(self):
        self.base = pkgroot + "/"
        if "EUPS_DIR" not in os.environ:
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)

    def testWebTransporter(self):
        loc = self.base+"s1/config.txt"
        localfile = "/tmp/eupstest-config.txt"
        if os.path.exists(localfile):
            os.remove(localfile)
        self.assert_(WebTransporter.canHandle(loc))

        trx = WebTransporter(loc)
        self.assertRaises(RemoteFileNotFound, trx.cacheToFile, localfile)
        self.assert_(not os.path.exists(localfile))

        loc = self.base+"s2/config.txt"
        trx = WebTransporter(loc)
        trx.cacheToFile(localfile)
        self.assert_(os.path.exists(localfile))

        loc = self.base+"s2"
        trx = WebTransporter(loc)
        files = trx.listDir()
        self.assertEquals(len(files), 2)
        self.assertIn("config.txt", files)
        self.assertIn("current.list", files)

from eups.distrib.server import DistribServer

class WebConfigFileTestCase(unittest.TestCase):

    def setUp(self):
        self.base = pkgroot + "/s2/"
        self.configFile = os.path.join(testEupsStack, "eups-config.txt")

    def tearDown(self):
        if os.path.exists(self.configFile):
            os.remove(self.configFile)

    def testGetConfigFile(self):
        ds = DistribServer(self.base)
        configFile = ds.getConfigFile(self.configFile)
        self.assert_(os.path.exists(configFile))



from eups.distrib.server import ServerConf

class WebServerConfTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgbase = pkgroot + "/s2/"
        self.servconf = ServerConf(self.pkgbase)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class WebDistribServerTestCase(unittest.TestCase):

    def setUp(self):
        self.pkgbase = pkgroot + "/s2/"
        self.ds = DistribServer(self.pkgbase)

    def tearDown(self):
        pass

    def testInit(self):
        pass

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
        self.assertEquals(len(tags), 1)
        self.assertIn("current", tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 1)
        self.assertIn("current", tags)


__all__ = "WebTransporterTestCase WebConfigFileTestCase WebServerConfTestCase WebDistribServerTestCase".split()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkgroot = sys.argv[1]
    unittest.main()
