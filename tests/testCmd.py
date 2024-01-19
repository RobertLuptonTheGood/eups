#!/usr/bin/env python
"""
Tests for eups.cmd
"""

# Import this first, as it will set up the environment
import testCommon

import os
import sys
import unittest
import re, shutil
from eups.utils import StringIO, encodePath
from testCommon import testEupsStack

import eups.cmd
import eups.hooks as hooks
from eups import Tag, TagNotRecognized
from eups.exceptions import ProductNotFound

prog = "eups"

class CmdTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()
        self.maxDiff = None
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.cmd._errstrm = self.err
        sys.stderr = self.err

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_PKGROOT"] = \
            os.path.join(testEupsStack,"testserver","s2")
        if "EUPS_FLAGS" in os.environ:
            del os.environ["EUPS_FLAGS"]

    def _resetOut(self):
        if isinstance(self.out, Stdout):
            del self.out; self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.cmd._errstrm = self.err

    def tearDown(self):
        del self.out

        os.environ = self.environ0

        newprod = os.path.join(self.dbpath,"newprod")
        if os.path.exists(newprod):
            for dir,subdirs,files in os.walk(newprod, False):
                for file in files:
                    os.remove(os.path.join(dir,file))
                for file in subdirs:
                    os.rmdir(os.path.join(dir,file))
            os.rmdir(newprod)

        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir20 = os.path.join(pdir, "2.0")
        if os.path.exists(pdir20):
            shutil.rmtree(pdir20)

    def testInit(self):
        eups.cmd.EupsCmd(args="-q".split(), toolname=prog)


    def testQuiet(self):
        cmd = eups.cmd.EupsCmd(args="-q".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")

    def testHelp(self):
        cmd = eups.cmd.EupsCmd(args="-h".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.out.getvalue(), "")
        self.assertTrue(re.match(r'^[Uu]sage: '+prog, self.err.getvalue()),
                     msg="Output starts with: '%s....'" % self.err.getvalue()[:16])

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -h".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.out.getvalue(), "")
        self.assertTrue(re.match(r'^[Uu]sage: '+prog+' flavor',
                              self.err.getvalue()),
                     msg="Output starts with: '%s....'" % self.err.getvalue()[:16])

    def testVersion(self):
        cmd = eups.cmd.EupsCmd(args="-V".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertTrue(self.out.getvalue().startswith("EUPS Version:"),
                     msg="Output starts with: '%s....'" % self.out.getvalue()[:16])

    def testFlavor(self):
        cmd = eups.cmd.EupsCmd(args="flavor".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertTrue(len(self.out.getvalue()) > 0)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -f Linux".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "Linux")

    def testPath(self):
        cmd = eups.cmd.EupsCmd(args="path".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), testEupsStack)

    def testPath2(self):
        cmd = eups.cmd.EupsCmd(args="pkgroot".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), os.environ["EUPS_PKGROOT"])

    def testFlags(self):
        cmd = eups.cmd.EupsCmd(args="flags".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "You have no EUPS_FLAGS set")


    def testList(self):
        outall = """
cfitsio               3006.2     \tcurrent
doxygen               1.5.7.1    \tcurrent
eigen                 2.0.0      \tcurrent
mpich2                1.0.5p4    \tcurrent
python                2.5.2      \tcurrent
python                2.6        """ """
tcltk                 8.5a4      \tcurrent
""".strip()
        outpy = """
   2.5.2      \tcurrent
   2.6
""".strip()
        outcurr = "\n".join(l for l in outpy.split("\n") if l.find('current') >= 0).strip()
        outnews = "\n".join(l for l in outpy.split("\n") if l.find('2.6') >= 0).strip()

        cmd = eups.cmd.EupsCmd(args="list".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), outall)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), outpy)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t current python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), outcurr)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t latest python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), outnews)

        # test the printing of the helpful message
        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list goober".split(), toolname=prog)
        try:
            self.assertEqual(cmd.run(), 1)
        except ProductNotFound as e:
            self.assertEqual(str(e), 'Unable to find product goober')

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list distrib goober".split(), toolname=prog)
        try:
            self.assertEqual(cmd.run(), 1)
        except ProductNotFound as e:
            self.assertEqual(str(e), 'Unable to find product distrib goober; Maybe you meant "eups distrib list"?')

        # test listing of LOCAL products
        self._resetOut()
        productRoot = os.path.join(testEupsStack, "Linux",
                                   "python", "2.5.2")
        eups.setup("python", productRoot=productRoot)
        outwlocal = """
   2.5.2      \tcurrent
   2.6        """ """
   LOCAL:%s \tsetup
""".strip() % encodePath(productRoot)
        cmd = eups.cmd.EupsCmd(args="list python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.out.getvalue(), outwlocal)
        self.assertEqual(self.err.getvalue(), "")
        eups.unsetup("python")

    def testListBadTag(self):
        if False:                       # just puts out a warning
            cmd = eups.cmd.EupsCmd(args="list tcltk -t goob".split(), toolname=prog)
            self.assertRaises(TagNotRecognized, cmd.run)

    def testUses(self):
        cmd = eups.cmd.EupsCmd(args="uses tcltk".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue([l for l in lines if pyuser.match(l)])

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses tcltk -t latest".split(),
                               toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue([l for l in lines if pyuser.match(l)])

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        lines = self.out.getvalue().split("\n")
        self.assertEqual(len(lines), 1)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertTrue(self.err.getvalue().find("Please specify a product name"))

    def testUsesBadTag(self):
        if False:                       # just puts out a warning
            cmd = eups.cmd.EupsCmd(args="uses tcltk -t goob".split(), toolname=prog)
            self.assertRaises(TagNotRecognized, cmd.run)

    def testDeclare(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        table = os.path.join(pdir10, "ups", "newprod.table")
        newprod = os.path.join(self.dbpath,"newprod")

        cmdargs = ["declare", "newprod", "1.0", "-r", pdir10, "-m", table]
        cmd = eups.cmd.EupsCmd(args=cmdargs, toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assertIsNotNone(prod, msg="Failed to declare product")
        self.assertEqual(prod.name,    "newprod")
        self.assertEqual(prod.version, "1.0")
        self.assertEqual(len(prod.tags), 1)   # current is tagged by default
        self.assertIn("current", prod.tags)
        self.assertTrue(os.path.isdir(newprod))

        # make sure user cannot set a server tag
        self._resetOut()
        cmd = "declare newprod 1.0 -t latest"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertNotEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        self._resetOut()
        cmd = "declare -F newprod 1.0 -t current"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assertIsNotNone(prod, msg="product went missing after tagging")
        self.assertIn("current", prod.tags)

        self._resetOut()
        cmd = "undeclare newprod 1.0"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assertIsNone(prod, "Failed to undeclare product")
        self.assertFalse(os.path.isdir(newprod))

        self._resetOut()
        cmdargs = ["declare", "newprod", "1.0", "-F", "-r", pdir10, "-m", table, "-t", "current"]
        cmd = eups.cmd.EupsCmd(args=cmdargs, toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assertIsNotNone(prod, msg="Failed to declare product")
        self.assertEqual(prod.name,    "newprod")
        self.assertEqual(prod.version, "1.0")
        self.assertEqual(len(prod.tags), 1)
        self.assertIn("current", prod.tags)
        self.assertTrue(os.path.isdir(newprod))

        self._resetOut()
        cmd = "undeclare newprod 1.0"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod", Tag("current"))
        self.assertIsNone(prod, msg="Failed to undeclare product")

    def testRemove(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "2.0")
        shutil.copytree(pdir10, pdir20)

        self.assertTrue(os.path.isdir(pdir20))

        eups.Eups().declare("newprod", "2.0", pdir20)
        self.assertTrue(os.path.exists(os.path.join(self.dbpath,"newprod","2.0.version")))

        cmd = eups.cmd.EupsCmd(args="remove newprod 2.0".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        self.assertEqual(self.out.getvalue(), "")
        prod = eups.Eups().findProduct("newprod", "2.0")
        self.assertIsNone(prod)
        self.assertFalse(os.path.isdir(pdir20))

    def testDistribList(self):
        cmd = eups.cmd.EupsCmd(args="distrib list".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        out = self.out.getvalue()
        self.assertTrue(len(out) > 0)
        self.assertTrue(out.find("No matching products") < 0)
        self.assertTrue(out.find("doxygen") >= 0)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="distrib list -f Linux".split(),
                               toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEqual(self.err.getvalue(), "")
        out = self.out.getvalue()
        self.assertTrue(len(out) > 0)
        self.assertTrue(out.find("No matching products") >= 0)

    def testDistrib(self):
        cmd = eups.cmd.EupsCmd(args="distrib".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertNotEqual(self.err.getvalue(), "")

import eups.setupcmd

class SetupCmdTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()

        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.setupcmd._errstrm = self.err

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_PKGROOT"] = \
            os.path.join(testEupsStack,"testserver","s2")
        if "EUPS_FLAGS" in os.environ:
            del os.environ["EUPS_FLAGS"]

    def _resetOut(self):
        if isinstance(self.out, Stdout):
            del self.out; self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.setupcmd._errstrm = self.err

    def tearDown(self):
        del self.out

        os.environ = self.environ0

#     def testQuiet(self):
#         cmd = eups.setupcmd.EupsSetup(args="-q".split(), toolname=prog)
#         self.assertNotEqual(cmd.run(), 0)
#         self.assertEqual(self.err.getvalue(), "")

    def testNoTable(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir11 = os.path.join(pdir, "1.1")

        cmdargs = ["-r", pdir11, "newprod"]
        hooks.config.Eups.defaultTags = dict(pre=[], post=[]) # disable any defined in the startup.py file
        cmd = eups.setupcmd.EupsSetup(args=cmdargs, toolname=prog)
        self.assertEqual(cmd.run(), 0)


class Stdout(object):

    def __init__(self, newstdout=None):
        self.oldstdout = sys.stdout
        if newstdout is None:
            newstdout = StringIO.StringIO()
        self.stdout = newstdout
        sys.stdout = self.stdout

    def getvalue(self):
        return self.stdout.getvalue().strip()

    def __del__(self):
        sys.stdout = self.oldstdout

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([CmdTestCase,
                                 SetupCmdTestCase
                                 ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
