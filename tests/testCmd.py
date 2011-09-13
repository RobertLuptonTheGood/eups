#!/usr/bin/env python
"""
Tests for eups.cmd
"""

import os
import sys
import unittest
import time
import re, shutil
import cStringIO as StringIO
import testCommon
from testCommon import testEupsStack

import eups.cmd
import eups.lock as lock
from eups import Tag, TagNotRecognized

prog = "eups"

class CmdTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()

        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.cmd._errstrm = self.err

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_PKGROOT"] = \
            os.path.join(testEupsStack,"testserver","s2")
        if os.environ.has_key("EUPS_FLAGS"):
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
        cmd = eups.cmd.EupsCmd(args="-q".split(), toolname=prog)
        

    def testQuiet(self):
        cmd = eups.cmd.EupsCmd(args="-q".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")

    def testHelp(self):
        cmd = eups.cmd.EupsCmd(args="-h".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.out.getvalue(), "")
        self.assert_(re.match(r'^[Uu]sage: '+prog, self.err.getvalue()),
                     "Output starts with: '%s....'" % self.err.getvalue()[:16])

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -h".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.out.getvalue(), "")
        self.assert_(re.match(r'^[Uu]sage: '+prog+' flavor',
                              self.err.getvalue()),
                     "Output starts with: '%s....'" % self.err.getvalue()[:16])

    def testVersion(self):
        cmd = eups.cmd.EupsCmd(args="-V".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(self.out.getvalue().startswith("EUPS Version:"),
                     "Output starts with: '%s....'" % self.out.getvalue()[:16])

    def testFlavor(self):
        cmd = eups.cmd.EupsCmd(args="flavor".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(len(self.out.getvalue()) > 0)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -f Linux".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "Linux")

    def testPath(self):
        cmd = eups.cmd.EupsCmd(args="path".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), testEupsStack)

    def testPath(self):
        cmd = eups.cmd.EupsCmd(args="pkgroot".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), os.environ["EUPS_PKGROOT"])

    def testFlags(self):
        cmd = eups.cmd.EupsCmd(args="flags".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "You have no EUPS_FLAGS set")
                          

    def testList(self):
        outall = """
cfitsio               3006.2     \tcurrent
doxygen               1.5.7.1    \tcurrent
eigen                 2.0.0      \tcurrent
mpich2                1.0.5p4    \tcurrent
python                2.5.2      \tcurrent
python                2.6        
tcltk                 8.5a4      \tcurrent
""".strip()
        outpy = """
   2.5.2      \tcurrent
   2.6        
""".strip()
        outcurr = "\n".join(filter(lambda l: l.find('current') >= 0, outpy.split("\n"))).strip()
        outnews = "\n".join(filter(lambda l: l.find('2.6') >= 0, outpy.split("\n"))).strip()

        cmd = eups.cmd.EupsCmd(args="list".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outall)
                          
        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outpy)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t current python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outcurr)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t newest python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outnews)

        # test the printing of the helpful message
        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list goober".split(), toolname=prog)
        self.assertEqual(cmd.run(), 1)
        self.assertEquals(self.out.getvalue(), "")
        self.assertEquals(self.err.getvalue(), prog + ' list: Unable to find product goober\n')

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list distrib goober".split(), toolname=prog)
        self.assertEqual(cmd.run(), 1)
        self.assertEquals(self.out.getvalue(), "")
        self.assertEquals(self.err.getvalue(), prog + ' list: Unable to find product distrib goober; Maybe you meant "eups distrib list"?\n')

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -q goober".split(), toolname=prog)
        self.assertEqual(cmd.run(), 1)
        self.assertEquals(self.out.getvalue(), "")
        self.assertEquals(self.err.getvalue(), "")

        # test listing of LOCAL products
        self._resetOut()
        eups.setup("python", productRoot=os.path.join(testEupsStack, "Linux",
                                                      "python", "2.5.2"))
        outwlocal = """
   2.5.2      \tcurrent
   2.6        
   LOCAL:%s/Linux/python/2.5.2 \tsetup
""".strip() % testEupsStack
        cmd = eups.cmd.EupsCmd(args="list python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.out.getvalue(), outwlocal)
        self.assertEquals(self.err.getvalue(), "")
        eups.unsetup("python")

    def testListBadTag(self):
        cmd = eups.cmd.EupsCmd(args="list tcltk -t goob".split(), 
                               toolname=prog)
#        self.assertNotEqual(cmd.run(), 0)
        # cmd is now raising exception
        self.assertRaises(TagNotRecognized, cmd.run)
#        self.assert_(self.err.getvalue().find("list: Unsupported tag") >= 0)

    def testUses(self):
        cmd = eups.cmd.EupsCmd(args="uses tcltk".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 2)
        self.assert_(filter(lambda l: pyuser.match(l), lines))

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses tcltk -t newest".split(), 
                               toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 2)
        self.assert_(filter(lambda l: pyuser.match(l), lines))

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses python".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 1)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assert_(self.err.getvalue().find("Please specify a product name"))

    def testUsesBadTag(self):
        cmd = eups.cmd.EupsCmd(args="uses tcltk -t goob".split(), 
                               toolname=prog)
#        self.assertNotEqual(cmd.run(), 0)
        # cmd is now raising exception
        self.assertRaises(TagNotRecognized, cmd.run)
#        self.assert_(self.err.getvalue().find("uses: Unsupported tag") >= 0)

    def testDeclare(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir11 = os.path.join(pdir, "1.1")
        table = os.path.join(pdir10, "ups", "newprod.table")
        newprod = os.path.join(self.dbpath,"newprod")

        cmd = "declare newprod 1.0 -r %s -m %s" % (pdir10, table)
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEquals(prod.name,    "newprod")
        self.assertEquals(prod.version, "1.0")
        self.assertEquals(len(prod.tags), 1)   # current is tagged by default
        self.assert_("current" in prod.tags)
        self.assert_(os.path.isdir(newprod))

        # make sure user cannot set a server tag
        self._resetOut()
        cmd = "declare newprod 1.0 -t newest"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertNotEqual(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        self._resetOut()
        cmd = "declare -F newprod 1.0 -t current"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is not None, "product went missing after tagging")
        self.assert_("current" in prod.tags)
        
        self._resetOut()
        cmd = "undeclare newprod 1.0"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is None, "Failed to undeclare product")
        self.assert_(not os.path.isdir(newprod))

        self._resetOut()
        cmd = "declare newprod 1.0 -F -r %s -m %s -t current" % (pdir10, table)
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEquals(prod.name,    "newprod")
        self.assertEquals(prod.version, "1.0")
        self.assertEquals(len(prod.tags), 1)
        self.assert_("current" in prod.tags)
        self.assert_(os.path.isdir(newprod))
        
        self._resetOut()
        cmd = "undeclare newprod 1.0"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod", Tag("current"))
        self.assert_(prod is None, "Failed to undeclare product")

    def testRemove(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "2.0")
        shutil.copytree(pdir10, pdir20)
        self.assert_(os.path.isdir(pdir20))

        eups.Eups().declare("newprod", "2.0", pdir20)
        self.assert_(os.path.exists(os.path.join(self.dbpath,"newprod","2.0.version")))
        
        cmd = eups.cmd.EupsCmd(args="remove newprod 2.0".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        prod = eups.Eups().findProduct("newprod", "2.0")
        self.assert_(prod is None)
        self.assert_(not os.path.isdir(pdir20))

    def testDistribList(self):
        cmd = eups.cmd.EupsCmd(args="distrib list".split(), toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        out = self.out.getvalue()
        self.assert_(len(out) > 0)
        self.assert_(out.find("No matching products") < 0)
        self.assert_(out.find("doxygen") >= 0)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="distrib list -f Linux".split(), 
                               toolname=prog)
        self.assertEqual(cmd.run(), 0)
        self.assertEquals(self.err.getvalue(), "")
        out = self.out.getvalue()
        self.assert_(len(out) > 0)
        self.assert_(out.find("No matching products") >= 0)

    def testDistrib(self):
        cmd = eups.cmd.EupsCmd(args="distrib".split(), toolname=prog)
        self.assertNotEqual(cmd.run(), 0)
        self.assertNotEquals(self.err.getvalue(), "")

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
        if os.environ.has_key("EUPS_FLAGS"):
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
#         self.assertEquals(self.err.getvalue(), "")

    def testNoTable(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir11 = os.path.join(pdir, "1.1")

        cmd = "-r %s newprod" % pdir11
        cmd = eups.setupcmd.EupsSetup(args=cmd.split(), toolname=prog)
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
