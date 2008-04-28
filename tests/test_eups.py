#!/usr/bin/env python
"""
Tests for eups
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import unittest
import neups

try:
    type(verbose)
except NameError:
    verbose = 0

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class tableTestCase(unittest.TestCase):
    """Test reading TableFiles"""
    def setUp(self):
        self.table = neups.Table("mwi.table")

    def tearDown(self):
        del self.table

    def testRead(self):
        """Test reading table files"""

        #print self.table

class oldTableTestCase(unittest.TestCase):
    """Test reading old-style TableFiles"""
    def setUp(self):
        self.table = neups.Table("dervish.table")

    def tearDown(self):
        del self.table

    def testRead(self):
        """Test reading table files"""

        #print self.table

class versionFileTestCase(unittest.TestCase):
    """Test reading version files"""
    def setUp(self):
        self.version = neups.Version("fw.version")

    def tearDown(self):
        del self.version

    def testRead(self):
        """Test reading version files"""

        #print self.version

class currentFileTestCase(unittest.TestCase):
    """Test reading current files"""
    def setUp(self):
        self.current = neups.Current("fw.current")

    def tearDown(self):
        del self.current

    def testRead(self):
        """Test reading current files"""

        self.assertTrue(self.info["DarwinX86"]["version"] == "svn3941")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    suites = []
    if False:
        suites += unittest.makeSuite(tableTestCase)
        suites += unittest.makeSuite(oldTableTestCase)
        suites += unittest.makeSuite(versionFileTestCase)
    suites += unittest.makeSuite(currentFileTestCase)

    return unittest.TestSuite(suites)

def run(exit=False):
    """Run the tests"""

    status = 0 if unittest.TextTestRunner().run(suite()).wasSuccessful() else 1

    if exit:
        sys.exit(status)
    else:
        return status

if __name__ == "__main__":
    run(True)
