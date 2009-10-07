#!/usr/bin/env python
"""
Tests for eups.cmd
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import unittest
import time
import re, shutil
import cStringIO as StringIO
from testCommon import testEupsStack

import eups.cmd
from eups import Tag

prog = "eups"

class CmdTestCase(unittest.TestCase):

    def setUp(self):
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.out = Stdout()
        self.err = StringIO.StringIO()
        eups.cmd._errstrm = self.err

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_PKGROOT"] = \
            os.path.join(testEupsStack,"testserver","s2")
        if os.environ.has_key("EUPS_FLAGS"):
            del os.environ["EUPS_FLAGS"]

    def _resetOut(self):
        if isinstance(self.out, Stdout):
            del self.out; self.out = Stdout()

    def tearDown(self):
        del self.out

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
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")

    def testHelp(self):
        cmd = eups.cmd.EupsCmd(args="-h".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(self.out.getvalue().startswith("Usage: eups "),
                     "Output starts with: '%s....'" % self.out.getvalue()[:16])

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -h".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(self.out.getvalue().startswith("Usage: eups flavor"),
                     "Output starts with: '%s....'" % self.out.getvalue()[:16])

    def testVersion(self):
        cmd = eups.cmd.EupsCmd(args="-V".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(self.out.getvalue().startswith("EUPS Version:"),
                     "Output starts with: '%s....'" % self.out.getvalue()[:16])

    def testFlavor(self):
        cmd = eups.cmd.EupsCmd(args="flavor".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assert_(len(self.out.getvalue()) > 0)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="flavor -f Linux".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "Linux")

    def testPath(self):
        cmd = eups.cmd.EupsCmd(args="path".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), testEupsStack)

    def testPath(self):
        cmd = eups.cmd.EupsCmd(args="pkgroot".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), os.environ["EUPS_PKGROOT"])

    def testFlags(self):
        cmd = eups.cmd.EupsCmd(args="flags".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "You have no EUPS_FLAGS set")
                          

    def testList(self):
        outall = """
cfitsio               3006.2    \tcurrent
doxygen               1.5.7.1   \tcurrent
eigen                 2.0.0     \tcurrent
mpich2                1.0.5p4   \tcurrent
python                2.5.2     \tcurrent
python                2.6       
tcltk                 8.5a4     \tcurrent
""".strip()
        outpy = """
   2.5.2     \tcurrent
   2.6       
""".strip()
        outcurr = "\n".join(filter(lambda l: l.find('current') >= 0, outpy.split("\n"))).strip()
        outnews = "\n".join(filter(lambda l: l.find('2.6') >= 0, outpy.split("\n"))).strip()

        cmd = eups.cmd.EupsCmd(args="list".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outall)
                          
        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list python".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outpy)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t current python".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outcurr)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="list -t newest python".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), outnews)

    def testListBadTag(self):
        cmd = eups.cmd.EupsCmd(args="list tcltk -t goob".split(), 
                               toolname=prog)
        cmd.run()
        self.assert_(self.err.getvalue().find("list: Unsupported tag"))

    def testUses(self):
        cmd = eups.cmd.EupsCmd(args="uses tcltk".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 2)
        self.assert_(filter(lambda l: pyuser.match(l), lines))

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses tcltk -t newest".split(), 
                               toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        pyuser = re.compile(r"python\s+2.5.2\s+8.5a4")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 2)
        self.assert_(filter(lambda l: pyuser.match(l), lines))

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses python".split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        lines = self.out.getvalue().split("\n")
        self.assertEquals(len(lines), 1)

        self._resetOut()
        cmd = eups.cmd.EupsCmd(args="uses".split(), toolname=prog)
        cmd.run()
        self.assert_(self.err.getvalue().find("Please specify a product name"))

    def testUsesBadTag(self):
        cmd = eups.cmd.EupsCmd(args="uses tcltk -t goob".split(), 
                               toolname=prog)
        cmd.run()
        self.assert_(self.err.getvalue().find("uses: Unsupported tag"))

    def testDeclare(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir11 = os.path.join(pdir, "1.1")
        table = os.path.join(pdir10, "ups", "newprod.table")
        newprod = os.path.join(self.dbpath,"newprod")

        cmd = "declare newprod 1.0 -r %s -m %s" % (pdir10, table)
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEquals(prod.name,    "newprod")
        self.assertEquals(prod.version, "1.0")
        self.assertEquals(len(prod.tags), 0)
        self.assert_("current" not in prod.tags)
        self.assert_(os.path.isdir(newprod))
        
        self._resetOut()
        cmd = "declare newprod 1.0 -t current"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        
        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is not None, "product went missing after tagging")
        self.assert_("current" in prod.tags)
        
        self._resetOut()
        cmd = "undeclare newprod 1.0"
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")

        myeups = eups.Eups()
        prod = myeups.findProduct("newprod")
        self.assert_(prod is None, "Failed to undeclare product")
        self.assert_(not os.path.isdir(newprod))

        self._resetOut()
        cmd = "declare newprod 1.0 -r %s -m %s -t current" % (pdir10, table)
        cmd = eups.cmd.EupsCmd(args=cmd.split(), toolname=prog)
        cmd.run()
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
        cmd.run()
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
        cmd.run()
        self.assertEquals(self.err.getvalue(), "")
        self.assertEquals(self.out.getvalue(), "")
        prod = eups.Eups().findProduct("newprod", "2.0")
        self.assert_(prod is None)
        self.assert_(not os.path.isdir(pdir20))

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


__all__ = "CmdTestCase".split()        

if __name__ == "__main__":
    unittest.main()
