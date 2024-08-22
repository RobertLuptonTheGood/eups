#!/usr/bin/env python
"""
A master script for running all tests.
"""

import unittest
import testCommon

tests = []
for t in [
    "test_app",
    "test_cmd",
    "test_deprecated",
    "test_db",
    "test_eups2",
    "test_misc",
    "test_product",
    "test_stack",
    "test_table",
    "test_tags",
    "test_eupspkg",
    "test_setups",
    "test_eups_integration",
    ]:
    tests += __import__(t).suite()

def run(shouldExit=False):
    testCommon.run(unittest.TestSuite(tests), shouldExit)

if __name__ == "__main__":
    run(True)
