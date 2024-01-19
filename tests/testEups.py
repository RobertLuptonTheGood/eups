#!/usr/bin/env python
"""
Tests for eups.Eups
"""

from __future__ import print_function

# Import this first, as it will set up the environment
import testCommon

import os
import sys
import shutil
import unittest
import tempfile
import time
from eups.utils import StringIO
from testCommon import testEupsStack

from eups import TagNotRecognized, ProductNotFound, EupsException
from eups.Eups import Eups
from eups.stack import ProductStack
from eups.utils import Quiet
import eups.hooks

class EupsTestCase(unittest.TestCase):

    def setUp(self):
        self.environ0 = os.environ.copy()

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_USERDATA"] = os.path.join(testEupsStack,"_userdata_")
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        eups.hooks.config.Eups.userTags = ['mine']
        self.eups = Eups()

        self.betachain = os.path.join(self.dbpath,"python","beta.chain")

    def tearDown(self):
        flavors = self.eups.versions[testEupsStack].getFlavors()
        for flav in flavors:
            file = os.path.join(self.dbpath, ProductStack.persistFilename(flav))
            if os.path.exists(file):
                os.remove(file)

        usercachedir = os.path.join(testEupsStack,"_userdata_","_caches_")
        if os.path.exists(usercachedir):
            shutil.rmtree(usercachedir, ignore_errors=True)

        if os.path.exists(self.betachain):  os.remove(self.betachain)

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

        eups.hooks.config.Eups.userTags = []

        os.environ = self.environ0

    def testInit(self):
        self.assertEqual(len(self.eups.path), 2)
        self.assertEqual(self.eups.path[0], testEupsStack)
        self.assertEqual(self.eups.path[1], os.environ["EUPS_USERDATA"])
        self.assertEqual(self.eups.getUpsDB(testEupsStack), self.dbpath)
        self.assertEqual(len(self.eups.versions), 2)
        self.assertIn(testEupsStack, self.eups.versions)
        self.assert_(self.eups.versions[testEupsStack] is not None)

        flavors = self.eups.versions[testEupsStack].getFlavors()
        self.assertEqual(len(flavors), 3)
        for flav in "Linux64 Linux generic".split():
            self.assertIn(flav, flavors)

        tags = self.eups.tags.getTagNames()
        exptags = "latest setup stable current commandLine keep path type version versionExpr warn"
        for tag in exptags.split():
            self.assertIn(tag, tags)

        self.assertEqual(len(self.eups.preferredTags), 5)
        for tag in "version versionExpr stable current latest".split():
            self.assertIn(tag, self.eups.preferredTags)

        # There should have been some cache files created
        # flavors.append("generic")
        for flav in flavors:
            cache = os.path.join(self.eups._userStackCache(testEupsStack),
                                 ProductStack.persistFilename(flav))
            self.assert_(os.path.exists(cache),
                         "Cache file for %s not written" % flav)

    def testPrefTags(self):
        self.assertRaises(TagNotRecognized,
                          self.eups.setPreferredTags, "goober gurn")
        self.eups.quiet = 1
        orig = self.eups.getPreferredTags()
        orig.sort()
        orig = " ".join(orig)
        self.eups._kindlySetPreferredTags("goober gurn")
        prefs = self.eups.getPreferredTags()
        prefs.sort()
        self.assertEqual(orig, " ".join(prefs))
        self.eups._kindlySetPreferredTags("goober stable gurn")
        self.assertEqual(" ".join(self.eups.getPreferredTags()), "stable")
        self.eups._kindlySetPreferredTags("stable beta")
        prefs = self.eups.getPreferredTags()
        prefs.sort()
        self.assertEqual(" ".join(prefs), "beta stable")

    def testFindProduct(self):

        # look for non-existent flavor
        prod = self.eups.findProduct("eigen", "2.0.0", flavor="Darwin")
        self.assert_(prod is None, "Found non-existent flavor")
        prod = self.eups.findProduct("eigen", "2.0.1", flavor="Linux")
        self.assert_(prod is None, "Found non-existent version")

        # find by name, version, flavor
        prod = self.eups.findProduct("eigen", "2.0.0", flavor="Linux")
        self.assert_(prod is not None, "Failed to find product")
        self.assertEqual(prod.name,    "eigen")
        self.assertEqual(prod.version, "2.0.0")
        self.assertEqual(prod.flavor,  "Linux")

        # look for non-existent name-version combo
        prod = self.eups.findProduct("eigen", "2.0.1")
        self.assert_(prod is None, "Found non-existent version")

        # find by name, version
        prod = self.eups.findProduct("eigen", "2.0.0")
        self.assert_(prod is not None, "Failed to find product")
        self.assertEqual(prod.name,    "eigen")
        self.assertEqual(prod.version, "2.0.0")
        self.assertEqual(prod.flavor,  "Linux")

        # find by name
        prod = self.eups.findProduct("eigen")
        self.assert_(prod is not None, "Failed to find product")
        self.assertEqual(prod.name,    "eigen")
        self.assertEqual(prod.version, "2.0.0")
        self.assertEqual(prod.flavor,  "Linux")
        self.assertIn("current", prod.tags)

        # find by name, preferring tagged version
        prod = self.eups.findProduct("python")
        self.assert_(prod is not None, "Failed to find python product")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor,  "Linux")
        self.assertIn("current", prod.tags)

        # find by name, preferring latest version
        tag = self.eups.tags.getTag("latest")
        prod = self.eups.findProduct("python", tag)
        self.assert_(prod is not None, "Failed to find python product")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.6")
        self.assertEqual(prod.flavor,  "Linux")
        self.assertEqual(len(prod.tags), 0)

        # find by name, expression
        prod = self.eups.findProduct("python", "< 2.6")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor,  "Linux")

        prod = self.eups.findProduct("python", ">= 2.6")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.6")
        self.assertEqual(prod.flavor,  "Linux")

        prod = self.eups.findProduct("python", ">= 2.5.2")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor,  "Linux")

        self.eups.setPreferredTags("latest")
        prod = self.eups.findProduct("python", ">= 2.5.2")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.6")
        self.assertEqual(prod.flavor,  "Linux")
        prod = self.eups.findProduct("python")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.6")
        self.assertEqual(prod.flavor,  "Linux")

        prod = self.eups.findProduct("python", "== 2.5.2")
        self.assertEqual(prod.name,    "python")
        self.assertEqual(prod.version, "2.5.2")
        self.assertEqual(prod.flavor,  "Linux")

        self.assertRaises(EupsException, self.eups.findProduct,
                          "python", "= 2.5.2")

        # look for a setup version
        tag = self.eups.tags.getTag("setup")
        prod = self.eups.findProduct("python", tag)
        self.assert_(prod is None, "Found unsetup product")

    def testAssignTags(self):
        prod = self.eups.getProduct("python", "2.6")
        self.assert_(prod is not None, "Failed to find python 2.6")
        if "beta" in prod.tags:
            print("Warning: python 2.6 is already tagged beta", file=sys.stderr)
        self.eups.assignTag("beta", "python", "2.6")

        self.assert_(os.path.exists(self.betachain),
                     "Failed to create beta tag file for python")
        prod = self.eups.getProduct("python", "2.6", noCache=True)
        self.assertIn("beta", prod.tags)
        prod = self.eups.getProduct("python", "2.6")
        self.assertIn("beta", prod.tags)

        # test unassign of tag to non-existent product
        self.assertRaises(ProductNotFound,
                          self.eups.unassignTag, "beta", "goober")

        # test unassign of tag to wrong version
        q = Quiet(self.eups)
        self.eups.unassignTag("beta", "python", "2.5.2")
        del q
        self.assert_(os.path.exists(self.betachain),
                     "Incorrectly removed beta tag file for python")

        # test unassign, specifying version
        self.eups.unassignTag("beta", "python", "2.6")
        self.assert_(not os.path.exists(self.betachain),
                     "Failed to remove beta tag file for python")

        # test unassign to any version
        self.eups.assignTag("beta", "python", "2.6")
        self.assert_(os.path.exists(self.betachain),
                     "Failed to create beta tag file for python")
        self.eups.unassignTag("beta", "python")
        self.assert_(not os.path.exists(self.betachain),
                     "Failed to remove beta tag file for python")
        prod = self.eups.findProduct("python", self.eups.tags.getTag("beta"))
        self.assert_(prod is None, "Failed to untag beta from %s" % prod)

    def testDeclare(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir11 = os.path.join(pdir, "1.1")
        table = os.path.join(pdir10, "ups", "newprod.table")
#        self.eups.verbose += 1

        # test declare.  Note: "current" is now a default tag assignment
        self.eups.declare("newprod", "1.0", pdir10, testEupsStack, table)
        prod = self.eups.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(prod.name,    "newprod")
        self.assertEqual(prod.version, "1.0")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], 'current')
        prod = self.eups.findProduct("newprod", noCache=True)
        self.assertEqual(prod.name,    "newprod")
        self.assertEqual(prod.version, "1.0")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], 'current')
        self.assert_(os.path.exists(os.path.join(self.dbpath,
                                                 "newprod", "1.0.version")))

        # test undeclare
        self.eups.undeclare("newprod", "1.0", testEupsStack)
        prod = self.eups.findProduct("newprod")
        self.assert_(prod is None, "Found undeclared product")
        prod = self.eups.findProduct("newprod", noCache=True)
        self.assert_(prod is None, "Found undeclared product")
        self.assert_(not os.path.exists(os.path.join(self.dbpath,
                                                     "newprod", "1.0.version")))

        # test declaring with tag (+ without eupsPathDir)
        self.eups.declare("newprod", "1.0", pdir10, None, table, tag="beta")
        prod = self.eups.findProduct("newprod", eupsPathDirs=testEupsStack)
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "beta")

        # test redeclaration with external file & "current" tag
        # We force a redclaration by adding the tag, but our primary aim here
        # is to check the machinery for handling external files.
        with tempfile.NamedTemporaryFile(delete=True) as extFile:
            extFileBaseName = os.path.basename(extFile.name)
            # We can't normally issue two identical declarations, but adding
            # the tag makes EUPS accept it.
            self.eups.declare("newprod", "1.0", pdir10, tag="current",
                              externalFileList=[(extFile.name, extFileBaseName)])
            self.eups.declare("newprod", "1.0", pdir10, tag="current",
                              externalFileList=[(extFile.name, extFileBaseName)])
            os.unlink(os.path.join(prod.extraProductDir(), extFileBaseName))
        self.eups.unassignTag("current", "newprod")

        # test 2nd declare, w/ transfer of tag
        self.eups.declare("newprod", "1.1", pdir11, None, table, tag="beta")
        prod = self.eups.findProduct("newprod", "1.1")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(prod.dir, pdir11)
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "beta")
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(len(prod.tags), 0)

        # test redeclare w/change of product dir
        prod = self.eups.findProduct("newprod", "1.1")
        self.assertRaises(EupsException, self.eups.declare, "newprod", "1.1", pdir10, None, table)
        # we can move the tag but not the directory
        self.eups.declare("newprod", "1.0", pdir11, None, table, tag="beta")
        self.assertEqual(self.eups.findProduct("newprod", self.eups.tags.getTag("beta")).dir, pdir10)
        # ...unless we force it
        self.eups.force = True
        self.eups.declare("newprod", "1.1", pdir10, None, table, tag="beta")
        prod = self.eups.findProduct("newprod", "1.1")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(prod.dir, pdir10)
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "beta")

        # test ambiguous undeclare
        self.assertRaises(EupsException, self.eups.undeclare, "newprod")

        # test tagging via declare (install dir determined on fly)
        self.eups.declare("newprod", "1.0", tag="current")
        chainfile = os.path.join(self.dbpath, "newprod", "current.chain")
        self.assert_(os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "current")

        # test unassign of tag via undeclare
        self.eups.undeclare("newprod", "1.0", tag="current")
        self.assert_(not os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Unintentionally undeclared product")
        self.assertEqual(len(prod.tags), 0)

        # test deprecated declareCurrent
        q = Quiet(self.eups)
        self.eups.declare ("newprod", "1.0", declareCurrent=True)
        self.assert_(os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "current")
        self.eups.undeclare("newprod", "1.0", undeclareCurrent=True)
        self.assert_(not os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Unintentionally undeclared product")
        self.assertEqual(len(prod.tags), 0)

        # test deprecated declareCurrent
        self.eups.declare("newprod", "1.0", pdir10, testEupsStack, table, True)
        self.assert_(os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Failed to declare product")
        self.assertEqual(len(prod.tags), 1)
        self.assertEqual(prod.tags[0], "current")
        self.eups.undeclare("newprod", "1.0", testEupsStack, True)
        self.assert_(not os.path.exists(chainfile))
        prod = self.eups.findProduct("newprod", "1.0")
        self.assert_(prod is not None, "Unintentionally undeclared product")
        self.assertEqual(len(prod.tags), 0)
        del q

        # test undeclare of tagged product
        self.eups.undeclare("newprod", "1.1")
        chainfile = os.path.join(self.dbpath, "newprod", "beta.chain")
        self.assert_(not os.path.exists(chainfile),
                     "undeclared tag file still exists")
        prod = self.eups.findTaggedProduct("newprod", "beta")
        self.assert_(prod is None, "removed tag still assigned")
        prod = self.eups.findProduct("newprod")
        self.assert_(prod is not None, "all products removed")

#       needs listProducts()
        self.eups.undeclare("newprod")
        self.assert_(not os.path.exists(os.path.join(self.dbpath,"newprod")),
                     "product not fully removed")

    def testDeclareStdinTable(self):
        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir11 = os.path.join(pdir, "1.1")
        tableStrm = StringIO.StringIO('setupRequired("python")\n')
        prod = self.eups.findProduct("newprod", "1.1")
        self.assert_(prod is None, "newprod is already declared")

        # declare with table coming from input stream
        self.eups.declare("newprod", "1.1", pdir11, testEupsStack, tableStrm)
        prod = self.eups.findProduct("newprod", "1.1")
        self.assert_(prod is not None, "failed to declare newprod 1.1")
        self.assertEqual(prod.tablefile,
                          os.path.join(self.dbpath, "Linux","newprod","1.1", "ups", "newprod.table"))

    def testUserTags(self):
        self.assert_(self.eups.tags.isRecognized("mine"),
                     "user:mine not recognized")
        prod = self.eups.getProduct("python", "2.5.2")
        self.assertNotIn("user:mine", prod.tags, "user:mine already assigned")
        self.eups.assignTag("mine", "python", "2.5.2")
        prod = self.eups.getProduct("python", "2.5.2")
        self.assertIn("user:mine", prod.tags, "user:mine not assigned")
        prod = self.eups.findProducts("python", tags="mine")
        self.assertEqual(len(prod), 1, "failed to find user-tagged product")
        self.assertEqual(prod[0].version, "2.5.2")
        self.eups.unassignTag("mine", "python", "2.5.2")
        #
        # unassignTag doesn't actually remove the file.  It probably should, but here it's
        # critical as otherwise the tests aren't idempotent
        #
        for eupsDb in self.eups.versions.keys():
            db = self.eups._databaseFor(eupsDb)
            try:
                vfile = db.getChainFile("mine", "python")
            except eups.ProductNotFound:
                continue

            try:
                os.unlink(vfile.file)
            except FileNotFoundError:
                pass
                
    def testList(self):

        # basic find
        prods = self.eups.findProducts("python")
        self.assertEqual(len(prods), 2)
        self.assertEqual(prods[0].name, "python")
        self.assertEqual(prods[0].version, "2.5.2")
        self.assertEqual(prods[1].name, "python")
        self.assertEqual(prods[1].version, "2.6")

        prods = self.eups.findProducts("python", tags="latest")
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0].name, "python")
        self.assertEqual(prods[0].version, "2.6")

        prods = self.eups.findProducts("py*", "2.*",)
        self.assertEqual(len(prods), 2)
        self.assertEqual(prods[0].name, "python")
        self.assertEqual(prods[0].version, "2.5.2")

        prods = self.eups.findProducts("python", "3.*",)
        self.assertEqual(len(prods), 0)

        # version and tags conflict; mutually exclusive
        prods = self.eups.findProducts("python", "2.5.2", tags="latest")
        self.assertEqual(len(prods), 0)

        prods = self.eups.findProducts("python", ">= 2.5.2")
        self.assertEqual(len(prods), 2)

        prods = self.eups.findProducts("python", ">= 2.5.2", tags="latest")
        self.assertEqual(len(prods), 1)

        prods = self.eups.findProducts("python", "<= 2.5.2", tags="latest")
        self.assertEqual(len(prods), 0)

        # find all: ['cfitsio','mpich2','eigen','python:2','doxygen','tcltk']
        prods = self.eups.findProducts()
        self.assertEqual(len(prods), 7)

        prods = self.eups.findProducts("python", tags="setup")
        self.assertEqual(len(prods), 0)

        prods = self.eups.findProducts("python", tags="current latest".split())
        self.assertEqual(len(prods), 2)

        prods = self.eups.findProducts("doxygen")
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0].name, "doxygen")
        self.assertEqual(prods[0].version, "1.5.7.1")
        prods = self.eups.findProducts("doxygen",
                                       flavors="Linux Linux64".split())
        self.assertEqual(len(prods), 2)
        self.assertEqual(prods[0].name, "doxygen")
        self.assertEqual(prods[0].version, "1.5.7.1")
        self.assertEqual(prods[1].name, "doxygen")
        self.assertEqual(prods[1].version, "1.5.9")

        # test deprecated function:
        q = Quiet(self.eups)
        prods = self.eups.listProducts("python", current=True)
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0].name, "python")
        self.assertEqual(prods[0].version, "2.5.2")
        del q

    def testSetup(self):
        # test getSetupProducts(), findSetupProduct(), findProducts(),
        # listProducts(), findSetupVersion()

        self.environ0 = os.environ.copy()

        self.eups.setup("python")
        self.assertIn("PYTHON_DIR", os.environ)
        self.assertIn("SETUP_PYTHON", os.environ)
        self.assertIn("TCLTK_DIR", os.environ)
        self.assertIn("SETUP_TCLTK", os.environ)

        self.eups.unsetup("python")
        self.assertNotIn("PYTHON_DIR", os.environ)
        self.assertNotIn("SETUP_PYTHON", os.environ)
        self.assertNotIn("TCLTK_DIR", os.environ)
        self.assertNotIn("SETUP_TCLTK", os.environ)

    def testRemove(self):
        os.environ = self.environ0

        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        pdir20 = os.path.join(pdir, "2.0")
        shutil.copytree(pdir10, pdir20)
        self.assert_(os.path.isdir(pdir20))

        self.eups.declare("newprod", "2.0", pdir20)
        self.assert_(os.path.exists(os.path.join(self.dbpath,"newprod","2.0.version")))
#        self.eups.verbose=1
#        self.eups.remove("newprod", "2.0", False, interactive=True)
        self.eups.remove("newprod", "2.0", False)
        self.assert_(not os.path.exists(os.path.join(self.dbpath,"newprod","2.0.version")),
                     "Failed to undeclare newprod")
        self.assert_(not os.path.exists(pdir20), "Failed to remove newprod")

        # need to test for recursion

class EupsCacheTestCase(unittest.TestCase):
    def setUp(self):
        self.environ0 = os.environ.copy()

        os.environ["EUPS_PATH"] = testEupsStack
        os.environ["EUPS_FLAVOR"] = "Linux"
        os.environ["EUPS_USERDATA"] = os.path.join(testEupsStack,"_userdata_")
        self.dbpath = os.path.join(testEupsStack, "ups_db")
        self.cache = os.path.join(self.dbpath,
                                  ProductStack.persistFilename("Linux"))
        if os.path.exists(self.cache):
            os.remove(self.cache)

        self.betachain = os.path.join(self.dbpath, "python", "beta.chain")

    def tearDown(self):
        usercachedir = os.path.join(testEupsStack,"_userdata_","_caches_")
        if os.path.exists(usercachedir):
            shutil.rmtree(usercachedir, ignore_errors=True)

        newprod = os.path.join(self.dbpath,"newprod")
        if os.path.exists(newprod):
            for dir,subdirs,files in os.walk(newprod, False):
                for file in files:
                    os.remove(os.path.join(dir,file))
                for file in subdirs:
                    os.rmdir(os.path.join(dir,file))
            os.rmdir(newprod)

        if os.path.exists(self.betachain):
            os.remove(self.betachain)

        os.environ = self.environ0

    def testDetectOutOfSync(self):
        e1 = Eups()
        e2 = Eups()
        time.sleep(1)

        prod = e1.findProduct("newprod")
        self.assert_(prod is None, "Found not-yet declared product")
        prod = e2.findProduct("newprod")
        self.assert_(prod is None, "Found not-yet declared product")

        pdir = os.path.join(testEupsStack, "Linux", "newprod")
        pdir10 = os.path.join(pdir, "1.0")
        table = os.path.join(pdir10, "ups", "newprod.table")
        e1.declare("newprod", "1.0", pdir10, testEupsStack, table)
        prod = e1.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")

        # Eups now keeps things in sync
        # prod = e2.findProduct("newprod")
        # self.assert_(prod is None, "Failed to consult out-of-sync cache")

        e2.assignTag("beta", "python", "2.5.2")
        prod = e2.findProduct("newprod")
        self.assert_(prod is not None, "Failed to declare product")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        EupsTestCase,
        EupsCacheTestCase
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
