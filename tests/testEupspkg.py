#!/usr/bin/env python
"""
Run tests of eupspkg, implemented as bash scripts in testEupspkg/ subdirectory
"""

import testCommon

EupspkgTest = testCommon.ScriptTestSuite("testEupspkg")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        EupspkgTest,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
