#!/usr/bin/env python
"""
Miscellaneous Tests.  These might eventually be migrated into other test
files.
"""
import os
import sys
import shutil
import re
import unittest
import time
import tempfile
import testCommon
from testCommon import testEupsStack

import eups
import eups.utils

class MiscTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testNothing(self):
        pass

class AtomicFileTestCase(unittest.TestCase):

    def setUp(self):
        self.workdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def testTempFileLocation(self):
        """The temporary file must be a sibling of the destination.

        A temporary file placed anywhere else risks a cross-filesystem
        rename, which is neither atomic nor guaranteed to succeed.
        """
        destdir = os.path.join(self.workdir, "sub")
        os.makedirs(destdir)
        dest = os.path.join(destdir, "out.txt")

        with eups.utils.AtomicFile(dest, "w") as fd:
            fd.write("some text")
            siblings = [f for f in os.listdir(destdir) if f.endswith(".tmp")]
            self.assertEqual(len(siblings), 1, "temp file not created alongside destination")
            self.assertEqual(os.listdir(self.workdir), ["sub"], "temp file leaked into parent")

        with open(dest) as fd:
            self.assertEqual(fd.read(), "some text")
        self.assertEqual(os.listdir(destdir), ["out.txt"])

    def testRelativeDestination(self):
        """A destination with no directory component writes to the cwd."""
        cwd = os.getcwd()
        os.chdir(self.workdir)
        try:
            with eups.utils.AtomicFile("out.txt", "w") as fd:
                fd.write("some text")
                self.assertTrue(any(f.endswith(".tmp") for f in os.listdir(".")))

            with open("out.txt") as fd:
                self.assertEqual(fd.read(), "some text")
            self.assertEqual(os.listdir("."), ["out.txt"])
        finally:
            os.chdir(cwd)

    def testCleanupOnError(self):
        """A failed write leaves no temporary file and creates no destination."""
        dest = os.path.join(self.workdir, "out.txt")

        with self.assertRaises(ValueError):
            with eups.utils.AtomicFile(dest, "w") as fd:
                fd.write("some text")
                raise ValueError("write failed")

        self.assertEqual(os.listdir(self.workdir), [])

    def testDestinationPreservedOnError(self):
        """A failed write must not disturb an existing destination."""
        dest = os.path.join(self.workdir, "out.txt")
        with open(dest, "w") as fd:
            fd.write("original")

        with self.assertRaises(ValueError):
            with eups.utils.AtomicFile(dest, "w") as fd:
                fd.write("replacement")
                raise ValueError("write failed")

        with open(dest) as fd:
            self.assertEqual(fd.read(), "original")
        self.assertEqual(os.listdir(self.workdir), ["out.txt"])

    def testCleanupOnInterrupt(self):
        """Cleanup also covers exceptions outside the Exception hierarchy."""
        dest = os.path.join(self.workdir, "out.txt")

        with self.assertRaises(KeyboardInterrupt):
            with eups.utils.AtomicFile(dest, "w") as fd:
                fd.write("some text")
                raise KeyboardInterrupt

        self.assertEqual(os.listdir(self.workdir), [])

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        MiscTestCase,
        AtomicFileTestCase,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
