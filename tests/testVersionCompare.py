#!/usr/bin/env python
"""
Tests for eups.VersionCompare
"""

import pdb                              # we may want to say pdb.set_trace()
import os
import sys
import unittest
import time
from testCommon import testEupsStack

from eups.NewVersionCompare import VersionCompare, NewVersionCompare
from eups import utils

class VersionCompareTestCase(unittest.TestCase):

    def setUp(self):
        self.vc = VersionCompare()
        self.newvc = NewVersionCompare()

    def testComparisons(self):
        self.matchImplementations('1.0', '1.0', 0)
        self.matchImplementations('1.0', '1.2')
        self.matchImplementations('1.2', '1.0', 1)
        self.matchImplementations('1.2', '2.0')
        self.matchImplementations('2.0', '1.2', 1)
        self.matchImplementations('1.2-1', '1.2')
        self.matchImplementations('1.2', '1.2-1', 1)
        self.matchImplementations('1.2-1', '1.2-4')
        self.matchImplementations('1.2-4', '1.2-1', 1)
        self.matchImplementations('1.2', '1.2+1')
        self.matchImplementations('1.2+1', '1.2', 1)
        self.matchImplementations('1.2+1', '1.2+4')
        self.matchImplementations('1.2+4', '1.2+1', 1)
        self.matchImplementations('1.2+1', '1.3')
        self.matchImplementations('1.3', '1.2+1', 1)
        self.matchImplementations('svn439', 'svn1002')
        self.matchImplementations('svn1002', 'svn439', 1)
        self.matchImplementations('1.2+svn1392', '1.2', 1)
        self.matchImplementations('1.3', 'myVersion')
        self.matchImplementations('1.2-1', '1.2')
        self.assertEquals(self.newvc('1.2-2-1', '1.2-2'), -1)
        self.assertEquals(self.newvc('1.2a', '1.2b'), -1)
        self.assertEquals(self.newvc('1.2', '1.2b'), -1)
        self.assertEquals(self.newvc('svn3991', 'cvs231'), 0)
        self.assertEquals(self.newvc('-21', '-44'), -1)
#        self.matchImplementations('1.2-1-1', '1.2-2')
#        self.matchImplementations('svn3991', 'cvs231')
#        self.matchImplementations('-21', '-44')

    def matchImplementations(self, v1, v2, c=-1):
        if utils.version_cmp(v1, v2) != c:
            raise RuntimeError("version_cmp('%s', '%s') != %s" % (v1,v2,c))
        old = self.vc(v1, v2) == c
        new = self.newvc(v1, v2) == c
        if not old and not new:
            raise RuntimeError("neither VCs work on ('%s', '%s')" % (v1,v2))
        if not old:
            raise RuntimeError("VC does not work on ('%s', '%s')" % (v1,v2))
        if not new:
            raise RuntimeError("NewVC does not work on ('%s', '%s')" % (v1,v2))
        return True


__all__ = "VersionCompareTestCase".split()        

if __name__ == "__main__":
    unittest.main()
