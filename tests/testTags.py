#!/usr/bin/env python
"""
Tests for eups.tags
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import unittest
import time
from testCommon import testEupsStack

from eups.tags import Tags, Tag, TagNotRecognized

class TagsTestCase(unittest.TestCase):

    def setUp(self):
        self.tags = Tags()
        self.tags.registerTag("stable")
        self.tags.registerUserTag("rlp")

    def testContents(self):
        tags = self.tags.getTagNames()
        self.assertEquals(len(tags), 2)
        self.assertEquals(tags[0], "stable")
        self.assertEquals(tags[1], "user:rlp")

    def testCmp(self):
        stable = self.tags.getTag("stable")
        self.assertEquals(stable, "stable")
        self.assertEquals(stable, stable)
        stable2 = self.tags.getTag("stable")
        self.assertEquals(stable, stable2)
        rlp = self.tags.getTag("rlp")
        self.assertNotEquals(stable, rlp)
        self.assertEquals("rlp", rlp)

    def testSaveLoad(self):
        file = os.path.join(testEupsStack, "ups_db", "test.tags")
        if os.path.exists(file):  os.remove(file)
        self.assert_(not os.path.exists(file))

        try: 
            self.tags.registerTag("current")
            self.tags.registerTag("beta")
            self.tags.save(self.tags.global_, file)
            self.assert_(os.path.exists(file))

            tags = Tags()
            tags.load(tags.global_, file)
            names = tags.getTagNames()
            self.assertEquals(len(names), 3)
            for tag in "stable current beta".split():
                self.assert_(tag in names, tag+" not found amoung loaded names")

        finally:
            if os.path.exists(file):  os.remove(file)

    def testSaveLoadUserTags(self):
        dir = os.path.join(testEupsStack, "ups_db")
        file = os.path.join(dir, Tags.persistFilename("user"))
        if os.path.exists(file):  os.remove(file)

        try: 
            self.tags.saveUserTags(dir)
            self.assert_(os.path.exists(file), "cache file not found: " + file)

            tags = Tags()
            tags.loadUserTags(dir)
            names = tags.getTagNames()
            self.assertEquals(len(names), 1)
            for tag in "user:rlp".split():
                self.assert_(tag in names, tag+" not found amoung loaded names")
        finally:
            if os.path.exists(file):  os.remove(file)

    def testSaveLoadGlobalTags(self):
        dir = testEupsStack
        file = os.path.join(dir, "ups_db",  Tags.persistFilename("global"))
        if os.path.exists(file):  os.remove(file)

        self.tags.registerTag("current")
        self.tags.registerTag("beta")
        self.tags.saveGlobalTags(dir)
        self.assert_(os.path.exists(file), "cache file not found: " + file)

        tags = Tags()
        tags.loadFromEupsPath(dir, 1)
        names = tags.getTagNames()
        self.assertEquals(len(names), 3)
        for tag in "stable current beta".split():
            self.assert_(tag in names, tag+" not found amoung loaded names")
        
        

if __name__ == "__main__":
    unittest.main()
