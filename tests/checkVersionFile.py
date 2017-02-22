#!/usr/bin/env python
"""
Check a Version file for parsability and macro substitution
"""

from __future__ import print_function
import os
import sys
import shutil
import re
import unittest
import time
from optparse import OptionParser
import testCommon

from eups import ProductNotFound, Product
from eups.db import VersionFile

defaultFile = os.path.join(testCommon.testEupsStack, "fw.version")
usrtablefiles = [ defaultFile ]

class CheckVersionFileTestCase(unittest.TestCase):
    flavre = re.compile(r"^\s*FLAVOR\s*=\s*")
    qualre = re.compile(r"^\s*QUALIFIERS\s*=\s*")
    def __init__(self, method=None, file=defaultFile, testExist=False,
                 prodroot=None):
        self.file = file
        self.testExist = testExist
        if not prodroot: prodroot = "/opt"
        self.prodroot = prodroot
        if method:
            unittest.TestCase.__init__(self, method)
        else:
            unittest.TestCase.__init__(self, 'testParsing')

    def setUp(self):
        self.vf = VersionFile(self.file)
        self.flavors = self._getFlavors(self.file)

    def tearDown(self):
        pass

    def _getFlavors(self, file):
        out = []
        fd = open(file)
        try:
            for line in fd:
                if self.flavre.match(line):
                    out.append(self.flavre.sub("", line).strip().strip('"').strip("'"))
                elif self.qualre.match(line) and len(out) > 0:
                    line = self.qualre.sub("", line).strip().strip('"').strip("'")
                    if len(line) > 0:
                        out[-1] += ":%s" % line
            return out

#            return map(lambda g: g.strip(),
#                       map(lambda f: self.flavre.sub("", f),
#                           filter(lambda l: self.flavre.match(l), fd)))

        finally:
            fd.close()

    def testParsing(self):
        for flavor in self.flavors:
            sys.stderr.write('+'); sys.stderr.flush()
            prod = self.vf.makeProduct(flavor, self.prodroot)
            self.assertPathOK(prod.dir, "prod.dir")
            self.assertPathOK(prod.db, "prod.db")
            self.assertPathOK(prod.tablefile, "prod.tablefile")

    def assertPathOK(self, path, what):
        self.assertResolvedMacros(path, what)
        self.assertAbs(path, what)
        if self.testExist:
            self.assertPathExists(path, what)

    def assertPathExists(self, path, what):
        self.assert_(os.path.exists(path),
                     "Path %s does not exist: %s" % (what, path))

    def assertResolvedMacros(self, path, what):
        self.assert_(path.find('$') < 0,
                     "Unresolved macro in %s: %s" % (what, path))
    def assertAbs(self, path, what):
        self.assert_(path == "none" or os.path.isabs(path),
                     "Relative path in %s: %s"  % (what, path))

    def shortDescription(self):
        return self.file

class VersionFileTestResult(unittest._TextTestResult):

    def __init__(self, stream=None):
        if not stream:
            stream = sys.stderr
        strm = unittest._WritelnDecorator(stream)
        unittest._TextTestResult.__init__(self, strm, True, 1)

def findVersionFiles(dir):
    out = []
    for subdir in os.walk(dir):
        out.extend(os.path.join(subdir[0], f) for f in [f for f in subdir[2] if f.endswith(".version")])
    return out

def handlefile(file, result, root=None, testExist=False):
    if not os.path.exists(file):
        raise RuntimeError("checkVersionFile: %s: file/dir not found" % file)

    if os.path.isdir(file):
        files = findVersionFiles(file)
        for each in files:
            handlefile(each, result, root, testExist)
    else:
        test = CheckVersionFileTestCase(file=file, testExist=testExist,
                                        prodroot=root)
        test.run(result)

__all__ = "CheckVersionFileTestCase".split()

if __name__ == "__main__":
    cli = OptionParser(usage="%prog [-p ROOTDIR] [-e] file/dir [...]")
    cli.add_option("-e", "--exists-test", action="store_true",
                   dest="testexist", default=False,
                   help="test if paths actually exist")
    cli.add_option("-p", "--product-root", action="store", dest="root",
                   help="root directory below which products are installed")
    (cli.opts, cli.args) = cli.parse_args()
    if cli.opts.root:  cli.opts.testexist = True


    result = VersionFileTestResult()

    for file in cli.args:
        try:
            handlefile(file, result, cli.opts.root, cli.opts.testexist)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)

    result.stream.writeln()
    plural = ["", "s"]
    nprobs = len(result.failures)+len(result.errors)
    if not result.wasSuccessful():
        result.printErrors()
        if nprobs != 1: plural.append(plural.pop(0))
        result.stream.writeln("%i file%s encountered problems; %i ok" %
                              (nprobs, plural[0], result.testsRun-nprobs))
    else:
        if result.testsRun != 1: plural.append(plural.pop(0))
        result.stream.writeln("%i file%s appear%s ok" %
                              (result.testsRun, plural[0], plural[1]))

