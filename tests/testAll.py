#!/usr/bin/env python
"""
A master script for running all tests.
"""

import unittest
import testCommon

tests = []
for t in [
    "testApp",
    "testCmd",
    "testDeprecated",
    "testDb",
    "testEups",
    "testMisc",
    "testProduct",
    "testStack",
    "testTable",
    "testTags",
    "testDyldLibraryPath",
    "testEupspkg",
    ]:
    tests += __import__(t).suite()

def run(shouldExit=False):
    testCommon.run(unittest.TestSuite(tests), shouldExit)

if __name__ == "__main__":
    run(True)
