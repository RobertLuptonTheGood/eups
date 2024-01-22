#!/usr/bin/env python
"""
Tests for eups
"""

import sys
import unittest
import eups

try:
    type(verbose)
except NameError:
    verbose = 0

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class tableTestCase(unittest.TestCase):
    """Test reading TableFiles"""
    def setUp(self):
        self.table = eups.Table("mwi.table")

    def tearDown(self):
        del self.table

    def testRead(self):
        """Test reading table files"""

        #print self.table

class oldTableTestCase(unittest.TestCase):
    """Test reading old-style TableFiles"""
    def setUp(self):
        self.table = eups.Table("dervish.table")

    def tearDown(self):
        del self.table

    def testRead(self):
        """Test reading table files"""

        #print self.table

class versionFileTestCase(unittest.TestCase):
    """Test reading version files"""
    def setUp(self):
        self.version = eups.VersionFile("fw.version")

    def tearDown(self):
        del self.version

    def testRead(self):
        """Test reading version files"""

        #print self.version

class currentFileTestCase(unittest.TestCase):
    """Test reading current files"""
    def setUp(self):
        self.current = eups.Current("fw.current")
        self.assertTrue = lambda x, y: x == y

    def tearDown(self):
        del self.current

    def testRead(self):
        """Test reading current files"""

        self.assertTrue(self.info["DarwinX86"]["version"] == "svn3941")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class versionOrdering(unittest.TestCase):
    """Test eups's version ordering"""

    def setUp(self):
        self.eups = eups.Eups()

    def tearDown(self):
        del self.eups

    def testVersions(self):
        # return -1 if v1 < v2; 0 if v1 == v2; 1 if v1 > v2
        tests = (
            ["aa", "==", "aa"],
            ["aa.2", ">", "aa.1"],
            ["aa.2.1", ">", "aa.2"],
            ["aa.2.1", "<", "aa.2.2"],
            ["aa.2.1", "<", "aa.3"],
            ["aa.2.b", ">", "aa.2.a"],
            ["aa.2.b", "<", "aa.2.c"],
            ["v1_0_0", ">", "1.0.2"],
            ["1_0_0", "<", "v1.0.2"],
            ["v1_0_3", "<", "a1.0.2"],
            ["v1_0_0", "<", "v1.0.2"],
            ["v1_0_3", ">", "v1.0.2"],
            ["v1_0_3", "==", "v1_0_3"],
            ["v1_0_3m1", "<", "v1_0_3"],
            ["v1_0_3p1", ">", "v1_0_3"],
            ["v2_0", ">", "v1_0"],
            ["v2_0", "<", "v3_0"],
            ["v1.2.3", "<", "v1.2.3+a"],
            ["v1.2-0", "<", "v1.2.3"],
            ["v1.2-4", "<", "v1.2.3"],
            ["1", ">", "1-a"],
            ["1", "<", "1+a"],
            ["1-a", "<", "1"],
            ["1-b", ">", "1-a"],
            ["1+a", "<", "1+b"],
            ["1-a", "<",  "1+a"],
            ["1+a", ">",  "1-a"],
            ["1-rc2+a", ">",  "1-rc2"],
            ["1-rc2+a", "<",  "1-rc2+b"],
            ["1", "==", "1"],
            ["1.2", ">",  "1.1"],
            ["1.2.1", ">",  "1.2"],
            ["1.2.1", "<",  "1.2.2"],
            ["1.2.1", "<",  "1.3"],
            ["1_0_2", ">",  "1.0.0"],
            ["1.2-rc1", "<",  "1.2"],
            ["1.2-rc1", "<",  "1.2-rc2"],
            ["1.2-rc1", "<",  "1.2.3"],
            ["1.2-rc4", "<",  "1.2.3"],
            ["1.2+h1", ">",  "1.2"],
            ["1.2-rc1+h1", ">",  "1.2-rc1"],
            ["1.2.3+svn666", ">",  "1.2.3"],
            ["1.2.3-svn666", "<",  "1.2.3"],
            ["1.2.3+svn666", ">",  "1.2.3+svn100"],
            ["1.2.3+svn666", "<",  "1.2.3+svn1000"],
            ["1.2.3+svn666", ">",  "1.2.3+rvn1000"],
            ["1.2.3+svn666", "==", "1.2.3+svn666"],
            ["1.2.3+svn666", "<",  "1.2.3+tvn666"],
            )

        if False:
            tests = (
                )

        nbad = 0
        for test in tests:
            vname, expected, v = test
            result = self.eups.version_cmp(vname, v)
            #print >> sys.stderr, "version_cmp(\"%s\", \"%s\") == %s" % (vname, v, result)
            if result == 0:
                result = "=="
            elif result == 1:
                result = ">"
            else:
                result = "<"

            if result != expected:
                nbad += 1
                print("%-10s %2s %-10s (expected %2s)" % (vname, result, v, expected), file=sys.stderr)

        assert(nbad == 0)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    suites = unittest.TestSuite()
    suites.addTest(unittest.makeSuite(tableTestCase))
    suites.addTest(unittest.makeSuite(oldTableTestCase))
    suites.addTest(unittest.makeSuite(versionFileTestCase))
    #suites.addTest(unittest.makeSuite(currentFileTestCase))
    suites.addTest(unittest.makeSuite(versionOrdering))

    return suites

def run(exit=False):
    """Run the tests"""

    if unittest.TextTestRunner().run(suite()).wasSuccessful():
        status = 0
    else:
        status = 1

    if exit:
        sys.exit(status)
    else:
        return status

if __name__ == "__main__":
    run(True)
