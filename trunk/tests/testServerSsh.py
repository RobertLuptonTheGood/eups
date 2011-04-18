#!/usr/bin/env python
"""
Tests for eups.server, focussing on scp tranport mechanisms
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import shutil
import unittest
import time
from testCommon import testEupsStack

from eups.distrib.server import Transporter, SshTransporter
from eups.distrib.server import RemoteFileNotFound

# the package server root:
pkgroot = "scp:dev.lsstcorp.org:/lsst/softstack/eupstest"

class SshTransporterTestCase(unittest.TestCase):

    def setUp(self):
        self.base = pkgroot + "/"
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

    def testSshTransporter(self):
        loc = self.base+"s1/config.txt"
        localfile = "/tmp/eupstest-config.txt"
        if os.path.exists(localfile):
            os.remove(localfile)
        self.assert_(SshTransporter.canHandle(loc))

        trx = SshTransporter(loc)
#        self.assertRaises(RemoteFileNotFound, trx.cacheToFile, localfile)
        self.assert_(not os.path.exists(localfile))

        loc = self.base+"s2/config.txt"
        trx = SshTransporter(loc)
        trx.cacheToFile(localfile)
        self.assert_(os.path.exists(localfile))
        
        loc = self.base+"s2"
        trx = SshTransporter(loc)
        files = trx.listDir()
        self.assertEquals(len(files), 2)
        self.assert_("config.txt" in files)
        self.assert_("current.list" in files)
        
from eups.distrib.server import DistribServer 

class SshConfigFileTestCase(unittest.TestCase):

    def setUp(self):
        self.base = pkgroot + "/s2"
        self.configFile = os.path.join(testEupsStack, "eups-config.txt")
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)

    def tearDown(self):
        if os.path.exists(self.configFile):
            os.remove(self.configFile)

    def testGetConfigFile(self):
        ds = DistribServer(self.base)
        configFile = ds.getConfigFile(self.configFile)
        self.assert_(os.path.exists(configFile))

        

from eups.distrib.server import ServerConf

class SshServerConfTestCase(unittest.TestCase):

    def setUp(self):
        os.environ["EUPS_PATH"] = testEupsStack
        self.pkgbase = pkgroot + "/s2"
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.servconf = ServerConf(self.pkgbase)

    def tearDown(self):
        pass

    def testGetConfigFile(self):
        pass

class SshDistribServerTestCase(unittest.TestCase):

    def setUp(self):
        self.pkgbase = pkgroot + "/s2"
        if not os.environ.has_key("EUPS_DIR"):
            os.environ["EUPS_DIR"] = os.path.dirname(testEupsStack)
        self.ds = DistribServer(self.pkgbase)

    def tearDown(self):
        pass

    def testInit(self):
        pass

    def testGetTagNames(self):
        # test default implementation
        tags = DistribServer.getTagNames(self.ds)
        self.assertEquals(len(tags), 1)
        self.assert_("current" in tags)

        # test configurable implementation (method 3)
        tags = self.ds.getTagNames()
        self.assertEquals(len(tags), 1)
        self.assert_("current" in tags)

__all__ = "SshTransporterTestCase SshConfigFileTestCase SshServerConfTestCase SshDistribServerTestCase".split()        

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkgroot = sys.argv[1]
    unittest.main()
