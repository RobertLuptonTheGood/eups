#!/usr/bin/env python
"""
Tests for eups.utils
"""

import unittest
import io

from eups import utils

class UtilsTestCase(unittest.TestCase):

    def testPass(self):
        pass

    def testConfigProperty(self):
        err = io.StringIO()
#        err = sys.stderr
        gen = utils.ConfigProperty("alpha beta gamma".split(), "gen", err)
        gen.beta = utils.ConfigProperty("delta epsilon".split(), "gen.beta",err)
        gen.alpha = 'a'
        gen.beta.delta = 'bd'
        gen.beta.epsilon = 'be'
        gen.gamma = 'c'
        gen.beta = 'b'   # should fail
        msg = "gen.beta: Cannot over-write property with sub-properties\n"
        self.assertEquals(err.getvalue(), msg)
        gen.beta.zeta = 'bz'  # should fail
        msg += "gen.beta.zeta: No such property name defined\n"
        self.assertEquals(err.getvalue(), msg)


__all__ = "UtilsTestCase".split()

if __name__ == "__main__":
    unittest.main()

