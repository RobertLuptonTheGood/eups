#!/usr/bin/env python
"""
Run spaces in paths tests, implemented as bash scripts in testSpaces/ subdirectory
"""

import testCommon

EupsSpacesTest = testCommon.ScriptTestSuite("testSpaces")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite(makeSuite=True):
    """Return a test suite"""

    return testCommon.makeSuite([
        EupsSpacesTest,
        ], makeSuite)

def run(shouldExit=False):
    """Run the tests"""
    testCommon.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
