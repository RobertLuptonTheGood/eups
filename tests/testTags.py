#!/usr/bin/env python
"""
Tests for eups.tags
"""
import os
import unittest

import testCommon
from testCommon import testEupsStack
from eups.tags import Tags, Tag, TagNotRecognized

class TagsTestCase(unittest.TestCase):

    def setUp(self):
        self.tags = Tags()
        self.tags.registerTag("stable")
        self.tags.registerUserTag("rlp")

    def testRecognized(self):
        self.assertTrue(self.tags.isRecognized("stable"), "stable not recognized")
        self.assertTrue(self.tags.isRecognized("global:stable"),
                     "global:stable not recognized")
        self.assertTrue(not self.tags.isRecognized("user:stable"),
                     "stable recognized as user tag")
        self.assertTrue(self.tags.isRecognized("rlp"), "rlp not recognized")
        self.assertTrue(self.tags.isRecognized("user:rlp"),
                     "user:rlp not recognized")
        self.assertTrue(not self.tags.isRecognized("global:rlp"),
                     "rlp recognized as global tag")

    def testGroupFor(self):
        self.assertEqual(self.tags.groupFor("stable"), Tags.global_)
        self.assertEqual(self.tags.groupFor("rlp"), Tags.user)
        self.assertTrue(self.tags.groupFor("goober") is None,
                     "Found group for undefined tag")

    def testTagNames(self):
        tags = self.tags.getTagNames()
        self.assertEqual(len(tags), 2)
        self.assertIn("stable", tags)
        self.assertIn("user:rlp", tags)

    def testGetTag(self):
        tag = self.tags.getTag("stable")
        self.assertTrue(isinstance(tag, Tag), "non-Tag returned by getTag()")
        self.assertEqual(tag.name, "stable")
        self.assertEqual(tag.group, Tags.global_)

        tag = self.tags.getTag("global:stable")
        self.assertTrue(isinstance(tag, Tag), "non-Tag returned by getTag()")
        self.assertEqual(tag.name, "stable")
        self.assertEqual(tag.group, Tags.global_)

        tag = self.tags.getTag("rlp")
        self.assertTrue(isinstance(tag, Tag), "non-Tag returned by getTag()")
        self.assertEqual(tag.name, "rlp")
        self.assertEqual(tag.group, Tags.user)

        tag = self.tags.getTag("user:rlp")
        self.assertTrue(isinstance(tag, Tag), "non-Tag returned by getTag()")
        self.assertEqual(tag.name, "rlp")
        self.assertEqual(tag.group, Tags.user)

        self.assertRaises(TagNotRecognized, self.tags.getTag, "goob")



    def testContents(self):
        tags = self.tags.getTagNames()
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], "stable")
        self.assertEqual(tags[1], "user:rlp")

    def testInit(self):
        t = Tags("setup latest")
        tags = t.getTagNames()
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], "latest")
        self.assertEqual(tags[1], "setup")

    def testCmp(self):
        stable = self.tags.getTag("stable")
        self.assertEqual(stable, "stable")
        self.assertEqual(stable, stable)
        stable2 = self.tags.getTag("stable")
        self.assertEqual(stable, stable2)
        rlp = self.tags.getTag("rlp")
        self.assertNotEqual(stable, rlp)
        self.assertEqual("rlp", rlp)

    def testSaveLoad(self):
        file = os.path.join(testEupsStack, "ups_db", "test.tags")
        if os.path.exists(file):  os.remove(file)
        self.assertTrue(not os.path.exists(file))

        try:
            self.tags.registerTag("current")
            self.tags.registerTag("beta")
            self.tags.save(self.tags.global_, file)
            self.assertTrue(os.path.exists(file))

            tags = Tags()
            tags.load(tags.global_, file)
            names = tags.getTagNames()
            self.assertEqual(len(names), 3)
            for tag in "stable current beta".split():
                self.assertIn(tag, names, tag+" not found amoung loaded names")

        finally:
            if os.path.exists(file):  os.remove(file)

    def testSaveLoadUserTags(self):
        dir = os.path.join(testEupsStack, "ups_db")
        file = os.path.join(dir, Tags.persistFilename("user"))
        if os.path.exists(file):  os.remove(file)

        self.assertEqual(len(self.tags.getTagNames()), 2)
        self.tags.loadUserTags(dir)
        self.assertEqual(len(self.tags.getTagNames()), 2)
        self.assertTrue(not os.path.exists(file))

        try:
            self.tags.saveUserTags(dir)
            self.assertTrue(os.path.exists(file), "cache file not found: " + file)

            tags = Tags()
            tags.loadUserTags(dir)
            names = tags.getTagNames()
            self.assertEqual(len(names), 1)
            for tag in "user:rlp".split():
                self.assertIn(tag, names, tag+" not found amoung loaded names")
        finally:
            if os.path.exists(file):  os.remove(file)

    def testSaveLoadGlobalTags(self):
        dir = testEupsStack
        file = os.path.join(dir, "ups_db",  Tags.persistFilename("global"))
        if os.path.exists(file):  os.remove(file)

        self.tags.registerTag("current")
        self.tags.registerTag("beta")
        self.tags.saveGlobalTags(dir)
        self.assertTrue(os.path.exists(file), "cache file not found: " + file)

        tags = Tags()
        tags.loadFromEupsPath(dir, 1)
        names = tags.getTagNames()
        self.assertEqual(len(names), 3)
        for tag in "stable current beta".split():
            self.assertIn(tag, names, tag+" not found amoung loaded names")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([TagsTestCase], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
